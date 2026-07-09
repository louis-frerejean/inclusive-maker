"""Affichage sur ecran QAPASS LCD1602 (I2C, backpack PCF8574) des ordres qui
seraient envoyes a la pompe - utilise pour la demo/soutenance (2026-07-09),
en l'absence de pompe et d'ESP32 physiquement branches (seul le LCD est sur
le breadboard). Reprend la meme machine a etats que l'ancien firmware ESP32 (Pomp_control_v3,
version Bluetooth retiree du depot une fois cette version validee - voir
l'historique git), y compris les transitions automatiques par duree, mais
l'affiche sur le LCD au lieu de piloter des relais pompe/vanne.

Remplace la premiere version ecrite pour un Grove LCD RGB Backlight v4.0 :
ce module s'est revele defectueux au test (2026-07-08, ligne SCL bloquee a
l'etat bas quel que soit le cablage - diagnostic confirme en debranchant le
Grove directement de l'ecran). Le QAPASS LCD1602 n'a pas de retroeclairage
RGB pilotable (juste allume/eteint, une seule couleur fixe), donc plus de
changement de couleur par etat ici - juste le texte.

Cablage : GND/VCC/SDA/SCL relies au bus I2C du Pi 5 (GPIO2=SDA, GPIO3=SCL).
VCC sur 3.3V (pas 5V : le Pi n'est pas tolerant 5V sur ses GPIO). Si le
contraste est trop faible en 3.3V, ajuster le petit potentiometre bleu au
dos du module plutot que de passer en 5V.

Adresse I2C par defaut : 0x27 (modifiable par les cavaliers A0/A1/A2 au dos
du module - si non detecte a 0x27 via `i2cdetect -y 1`, relever l'adresse
reellement affichee et la passer via GANT_LCD_I2C_ADDR).

Protocole : backpack PCF8574 pilotant un controleur HD44780 standard en
mode 4 bits. Brochage PCF8574 -> HD44780 (convention universelle de ces
backpacks) : P0=RS, P1=RW (toujours a 0, ecriture seule), P2=E,
P3=retroeclairage, P4-P7=D4-D7 (nibble haut).
"""
import os
import threading
import time

from smbus2 import SMBus

LCD_ADDR = int(os.environ.get("GANT_LCD_I2C_ADDR", "0x27"), 16)
I2C_BUS = int(os.environ.get("GANT_LCD_I2C_BUS", "1"))

RS_BIT = 0x01
E_BIT = 0x04
BACKLIGHT_BIT = 0x08

DUREE_GONFLAGE_S = 8.0
DUREE_DESSERRAGE_S = 5.0
DUREE_REGONFLAGE_S = 2.0

INACTIF, SERRAGE, DESSERRAGE, STOP, REGONFLAGE, ARRET_URGENCE = (
    "INACTIF", "SERRAGE", "DESSERRAGE", "STOP", "REGONFLAGE", "ARRET_URGENCE",
)

# Ligne 2 (16 caracteres max) par etat : les etats de transition (pompe en
# train de tourner) affichent une action en cours ("..."), les etats stables
# affichent la position de la main (ouverte/fermee).
_ETAT_LIGNE2 = {
    INACTIF:       "MAIN OUVERTE",
    SERRAGE:       "FERMETURE...",
    DESSERRAGE:    "OUVERTURE...",
    STOP:          "MAIN FERMEE",
    REGONFLAGE:    "RECHARGE...",
    ARRET_URGENCE: "URGENCE !",
}

ECOUTE_TEXTE = "A L'ECOUTE..."


class LcdLink:
    """Meme interface que GantLink (serrer/desserrer/stop/regonfler/urgence/
    close), pour rester compatible avec keyword_actions.py sans le modifier
    autrement que l'import. Pas de connect() ni de PING ici : pas de liaison
    a maintenir, le LCD est ecrit en direct a chaque changement d'etat.

    Ecran divise en deux lignes independantes :
      - ligne 1 : uniquement l'etat d'ecoute du mot declencheur (vide si
        hors fenetre d'ecoute) - pilotee par set_ecoute(), appelee depuis
        keyword_actions.py.
      - ligne 2 : etat de la pompe (action en cours ou position stable de
        la main) - pilotee par les methodes serrer/desserrer/stop/... comme
        avant.
    """

    def __init__(self, addr=LCD_ADDR, bus=I2C_BUS):
        self._addr = addr
        self._i2c = SMBus(bus)
        self._lock = threading.Lock()
        self._timer = None
        self._etat = None
        self._urgence_ts = None
        self._init_lcd()
        self._set_ligne(0, "")
        self._changer_etat(INACTIF, "demarrage")

    def _write_byte(self, bits):
        self._i2c.write_byte(self._addr, bits | BACKLIGHT_BIT)

    def _write4(self, bits):
        # Pulse du signal Enable : le HD44780 lit les 4 bits de donnees sur
        # le front descendant de E.
        self._write_byte(bits)
        self._write_byte(bits | E_BIT)
        time.sleep(0.0005)
        self._write_byte(bits)
        time.sleep(0.0001)

    def _send(self, data, rs):
        self._write4(rs | (data & 0xF0))
        self._write4(rs | ((data << 4) & 0xF0))

    def _command(self, cmd):
        self._send(cmd, 0x00)

    def _write_char(self, char):
        self._send(ord(char), RS_BIT)

    def _init_lcd(self):
        time.sleep(0.05)
        # Sequence de reset standard HD44780 (voir datasheet, mode 4 bits).
        self._write4(0x30)
        time.sleep(0.005)
        self._write4(0x30)
        time.sleep(0.001)
        self._write4(0x30)
        time.sleep(0.001)
        self._write4(0x20)   # passage en mode 4 bits
        self._command(0x28)  # 4 bits, 2 lignes, police 5x8
        self._command(0x0C)  # affichage on, curseur/clignotement off
        self._command(0x06)  # increment, pas de decalage
        self._command(0x01)  # clear
        time.sleep(0.002)

    def _set_ligne(self, num, texte):
        # Complete a 16 caracteres avec des espaces pour effacer tout residu
        # d'un texte plus long affiche precedemment sur cette ligne (pas de
        # clear ici : on ne touche pas l'autre ligne).
        texte = texte[:16].ljust(16)
        self._command(0x80 if num == 0 else 0xC0)  # debut ligne 1 / ligne 2
        for c in texte:
            self._write_char(c)

    def set_ecoute(self, actif):
        """Ligne 1, independante de l'etat de la pompe : vide hors fenetre
        d'ecoute, message fixe pendant la fenetre. Appelee depuis
        keyword_actions.py a l'ouverture/fermeture de la fenetre d'ecoute."""
        with self._lock:
            self._set_ligne(0, ECOUTE_TEXTE if actif else "")

    def _appliquer_etat(self, etat):
        self._set_ligne(1, _ETAT_LIGNE2[etat])

    def _changer_etat(self, nouvel_etat, raison, duree_auto=None, etat_suivant=None):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            self._etat = nouvel_etat
            self._appliquer_etat(nouvel_etat)
            print(f"[LCD] -> {nouvel_etat} ({raison})")
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
        with self._lock:
            self._urgence_ts = time.monotonic()
        self._changer_etat(ARRET_URGENCE, "commande vocale URGENCE")

    def reset(self):
        """Reset manuel vers INACTIF - jamais appele automatiquement, sur
        action explicite seulement (bouton physique en ARRET_URGENCE, voir
        pump_link.py). Doit rester synchronise avec la meme logique dans
        pump_link.py: si moins de DUREE_DESSERRAGE_S s'est ecoulee depuis
        l'urgence, la main n'a pas fini de se depressuriser physiquement -
        afficher "MAIN OUVERTE" tout de suite serait faux, on affiche donc
        "OUVERTURE..." (DESSERRAGE) le temps restant avant de declarer
        INACTIF."""
        with self._lock:
            started = self._urgence_ts
        elapsed = time.monotonic() - started if started else DUREE_DESSERRAGE_S
        remaining = max(0.0, DUREE_DESSERRAGE_S - elapsed)
        if remaining > 0:
            self._changer_etat(DESSERRAGE, "reset (fin de depressurisation)", remaining, INACTIF)
        else:
            self._changer_etat(INACTIF, "reset (bouton apres urgence)")

    def close(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
        try:
            self._command(0x01)   # clear
            self._i2c.write_byte(self._addr, 0x00)  # coupe le retroeclairage
        finally:
            self._i2c.close()
