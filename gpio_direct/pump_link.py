"""Pilotage direct pompe/vanne + lecture du bouton poussoir physique, via
les GPIO du Raspberry Pi 5 - remplace l'ESP32 pour la demo finale (materiel
fourni par Cecile : module relais 2 canaux + bouton poussoir, 5 fils : 5V,
GND, Valve, Pompe, Bouton).

ATTENTION SECURITE (gant reellement porte pendant la demo) : contrairement
a l'ESP32 (fail-safe materiel independant - watchdog PING Bluetooth, meme
si le Pi plante), ce module tourne dans le meme processus Python que la
reconnaissance vocale. Si ce processus plante ou se bloque pendant que le
relais pompe est actif, RIEN ne le coupe automatiquement - le bouton
poussoir non plus, puisqu'il est lu par ce meme processus. Les seules
protections restantes sont logicielles : coupure automatique apres duree
fixe (comme sur l'ESP32) et le bouton (tant que le process tourne). A
verifier avec Cecile si un coupe-circuit materiel independant du Pi est
possible en complement.

Reprend la machine a etats et les durees du firmware ESP32
(bluetooth_esp32/arduino/Pomp_control_V3/.../Pomp_control_v3.ino) :
  INACTIF       : pompe OFF, vanne ON  (repos, aucune pression)
  SERRAGE       : pompe ON,  vanne OFF (monte en pression, 8s puis -> STOP)
  DESSERRAGE    : pompe OFF, vanne ON  (relache la pression, 5s puis -> INACTIF)
  STOP          : pompe OFF, vanne OFF (maintien de la pression actuelle)
  REGONFLAGE    : pompe ON,  vanne OFF (recharge courte, 2s puis -> STOP)
  ARRET_URGENCE : pompe OFF, vanne ON  (securite, depressurisation totale)

Bouton poussoir (comme sur l'ESP32) : un appui force ARRET_URGENCE depuis
n'importe quel etat ; un second appui (en ARRET_URGENCE) reinitialise vers
INACTIF - reset manuel volontaire, jamais automatique.

Brochage (a verifier/adapter au cablage reel - valeurs par defaut
arbitraires) : GANT_GPIO_POMPE_PIN, GANT_GPIO_VANNE_PIN,
GANT_GPIO_BOUTON_PIN. VCC du module relais sur 5V (pas les broches de
signal, qui restent en 3.3V - meme schema que l'ESP32, qui pilotait deja
ces memes relais en logique 3.3V).
"""
import os
import threading

from gpiozero import Button, OutputDevice

POMPE_PIN = int(os.environ.get("GANT_GPIO_POMPE_PIN", "17"))
VANNE_PIN = int(os.environ.get("GANT_GPIO_VANNE_PIN", "27"))
BOUTON_PIN = int(os.environ.get("GANT_GPIO_BOUTON_PIN", "22"))

DUREE_GONFLAGE_S = 8.0
DUREE_DESSERRAGE_S = 5.0
DUREE_REGONFLAGE_S = 2.0

INACTIF, SERRAGE, DESSERRAGE, STOP, REGONFLAGE, ARRET_URGENCE = (
    "INACTIF", "SERRAGE", "DESSERRAGE", "STOP", "REGONFLAGE", "ARRET_URGENCE",
)


class PumpLink:
    """Meme interface que GantLink/LcdLink (serrer/desserrer/stop/regonfler/
    urgence/close), pour rester compatible avec keyword_actions.py. Prend en
    plus deux callbacks optionnels (on_bouton_urgence, on_bouton_reset)
    appeles depuis le thread d'ecoute du bouton, pour que tout le systeme
    (LCD, visuel web, ce module) reagisse au bouton physique - pas
    seulement le relais pompe/vanne."""

    def __init__(self, pompe_pin=POMPE_PIN, vanne_pin=VANNE_PIN,
                 bouton_pin=BOUTON_PIN, on_bouton_urgence=None, on_bouton_reset=None):
        # active_high=False : reprend la polarite RELAIS_ON=LOW du firmware
        # ESP32 - a verifier sur le module relais fourni par Cecile.
        self._pompe = OutputDevice(pompe_pin, active_high=False, initial_value=False)
        self._vanne = OutputDevice(vanne_pin, active_high=False, initial_value=False)
        self._lock = threading.Lock()
        self._timer = None
        self._etat = None
        self._on_bouton_urgence = on_bouton_urgence
        self._on_bouton_reset = on_bouton_reset

        self._bouton = Button(bouton_pin, pull_up=True, bounce_time=0.05)
        self._bouton.when_pressed = self._bouton_presse

        self._changer_etat(INACTIF, "demarrage")

    def _bouton_presse(self):
        print("[BOUTON] Appui detecte")
        with self._lock:
            en_urgence = self._etat == ARRET_URGENCE
        if en_urgence:
            (self._on_bouton_reset or self.reset)()
        else:
            (self._on_bouton_urgence or self.urgence)()

    def _appliquer_etat(self, etat):
        if etat in (INACTIF, DESSERRAGE, ARRET_URGENCE):
            self._pompe.off()
            self._vanne.on()
        elif etat in (SERRAGE, REGONFLAGE):
            self._pompe.on()
            self._vanne.off()
        elif etat == STOP:
            self._pompe.off()
            self._vanne.off()

    def _changer_etat(self, nouvel_etat, raison, duree_auto=None, etat_suivant=None):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            self._etat = nouvel_etat
            self._appliquer_etat(nouvel_etat)
            print(
                f"[POMPE] -> {nouvel_etat} ({raison}) "
                f"pompe={'ON' if self._pompe.value else 'OFF'} "
                f"vanne={'ON' if self._vanne.value else 'OFF'}"
            )
            if duree_auto and etat_suivant:
                self._timer = threading.Timer(
                    duree_auto, self._changer_etat,
                    args=(etat_suivant, f"{nouvel_etat} termine"),
                )
                self._timer.daemon = True
                self._timer.start()

    def reset(self):
        """Reset manuel vers INACTIF - jamais appele automatiquement, sur
        action explicite seulement (bouton en ARRET_URGENCE)."""
        self._changer_etat(INACTIF, "reset (bouton apres urgence)")

    def serrer(self):
        with self._lock:
            etat = self._etat
        if etat in (INACTIF, STOP):
            self._changer_etat(SERRAGE, "commande vocale SERRER", DUREE_GONFLAGE_S, STOP)
        else:
            print(f"[CMD] Ignoree : SERRER invalide depuis {etat}")

    def desserrer(self):
        with self._lock:
            etat = self._etat
        if etat in (STOP, SERRAGE):
            self._changer_etat(DESSERRAGE, "commande vocale DESSERRER", DUREE_DESSERRAGE_S, INACTIF)
        else:
            print(f"[CMD] Ignoree : DESSERRER invalide depuis {etat}")

    def stop(self):
        with self._lock:
            etat = self._etat
        if etat in (SERRAGE, DESSERRAGE, REGONFLAGE):
            self._changer_etat(STOP, "commande vocale STOP")
        else:
            print(f"[CMD] Ignoree : STOP invalide depuis {etat}")

    def regonfler(self):
        with self._lock:
            etat = self._etat
        if etat == ARRET_URGENCE:
            print("[CMD] Ignoree : REGONFLER invalide depuis ARRET_URGENCE")
            return
        self._changer_etat(REGONFLAGE, "commande vocale REGONFLER", DUREE_REGONFLAGE_S, STOP)

    def urgence(self):
        self._changer_etat(ARRET_URGENCE, "commande vocale URGENCE")

    def close(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
        self._pompe.close()
        self._vanne.close()
        self._bouton.close()
