"""Pilotage direct de la pompe/vanne depuis les GPIO du Raspberry Pi 5, sans
passer par un ESP32 intermediaire.

EXPERIMENTAL - piste exploree suite a l'achat d'une carte d'extension GPIO
(montee sur breadboard, 2026-07-08). Ne remplace PAS bluetooth_esp32/, la
version utilisee pour la soutenance du 2026-07-09 : ce fichier n'a jamais
ete teste sur la pompe reelle, et il perd l'isolation de securite
qu'apportait l'ESP32 (watchdog independant du Pi - voir PING_TIMEOUT_MS
dans Pomp_control_v3.ino). Si le Pi plante ou gele, plus rien ne coupe la
pompe automatiquement ici : il faudrait un watchdog materiel separe avant
de brancher une pompe reelle sur ce chemin.

Reprend les etats et durees du firmware ESP32 de Cecile (voir
bluetooth_esp32/arduino/Pomp_control_V3/.../Pomp_control_v3.ino) mais pilote
les relais pompe/vanne directement en GPIO au lieu de les piloter par
Bluetooth.

Brochage : GANT_GPIO_POMPE_PIN / GANT_GPIO_VANNE_PIN ci-dessous sont des
valeurs par defaut arbitraires (numerotation BCM), PAS ENCORE VERIFIEES
contre le cablage reel de la carte d'extension + breadboard. A adapter
avant tout test avec un vrai relais.

Utilise gpiozero plutot que RPi.GPIO : RPi.GPIO n'est pas compatible
nativement avec le chip GPIO du Pi 5 (RP1) sauf a passer par un backend
lgpio - gpiozero gere cette selection automatiquement.
"""
import os
import threading

from gpiozero import OutputDevice

POMPE_PIN = int(os.environ.get("GANT_GPIO_POMPE_PIN", "17"))
VANNE_PIN = int(os.environ.get("GANT_GPIO_VANNE_PIN", "27"))

DUREE_GONFLAGE_S = 8.0
DUREE_DESSERRAGE_S = 5.0
DUREE_REGONFLAGE_S = 2.0

INACTIF, SERRAGE, DESSERRAGE, STOP, REGONFLAGE, ARRET_URGENCE = (
    "INACTIF", "SERRAGE", "DESSERRAGE", "STOP", "REGONFLAGE", "ARRET_URGENCE",
)


class GpioLink:
    """Meme interface que GantLink (serrer/desserrer/stop/regonfler/urgence/
    close), pour rester compatible avec keyword_actions.py. Pas de connect()
    ni de PING ici : plus de liaison Bluetooth a maintenir, les relais sont
    pilotes en direct."""

    def __init__(self, pompe_pin=POMPE_PIN, vanne_pin=VANNE_PIN):
        # active_high=False : reprend la polarite RELAIS_ON=LOW du firmware
        # ESP32 - a verifier sur le relais reellement cable sur la carte
        # d'extension (peut etre actif haut selon le module).
        self._pompe = OutputDevice(pompe_pin, active_high=False, initial_value=False)
        self._vanne = OutputDevice(vanne_pin, active_high=False, initial_value=False)
        self._lock = threading.Lock()
        self._timer = None
        self._etat = None
        self._changer_etat(INACTIF, "demarrage")

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
                f"[ETAT] -> {nouvel_etat} ({raison}) "
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
