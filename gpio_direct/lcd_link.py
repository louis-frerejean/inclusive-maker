"""Affichage sur ecran Grove LCD RGB Backlight v4.0 (I2C) des ordres qui
seraient envoyes a la pompe - utilise pour la demo/soutenance (2026-07-09),
en l'absence de pompe et d'ESP32 physiquement branches (seul le LCD est sur
le breadboard). Reprend la meme machine a etats que le firmware ESP32 (voir
bluetooth_esp32/arduino/Pomp_control_V3/.../Pomp_control_v3.ino), y compris
les transitions automatiques par duree, mais l'affiche sur le LCD au lieu de
piloter des relais pompe/vanne.

Cablage : Grove LCD RGB Backlight v4.0 sur breadboard, relie au bus I2C du
Pi 5 (GPIO2=SDA, GPIO3=SCL, + alimentation 5V/GND). Le module expose deux
peripheriques I2C a des adresses fixes :
    0x3E -> controleur texte (identique sur toutes les versions du module)
    0x30 -> controleur retroeclairage RGB (0x30 sur le v4.0 ; 0x62 sur
            l'ancien v2.0 - a verifier avec `i2cdetect -y 1` si l'ecran
            reste blanc/eteint, et corriger via GANT_LCD_RGB_ADDR si besoin)

Activer l'I2C au prealable sur le Pi (`sudo raspi-config` -> Interface
Options -> I2C), puis verifier que le module est bien vu :
    sudo i2cdetect -y 1
"""
import os
import threading
import time

from smbus2 import SMBus

LCD_ADDR = 0x3E
RGB_ADDR = int(os.environ.get("GANT_LCD_RGB_ADDR", "0x30"), 16)
I2C_BUS = int(os.environ.get("GANT_LCD_I2C_BUS", "1"))

DUREE_GONFLAGE_S = 8.0
DUREE_DESSERRAGE_S = 5.0
DUREE_REGONFLAGE_S = 2.0

INACTIF, SERRAGE, DESSERRAGE, STOP, REGONFLAGE, ARRET_URGENCE = (
    "INACTIF", "SERRAGE", "DESSERRAGE", "STOP", "REGONFLAGE", "ARRET_URGENCE",
)

# (texte 2 lignes, couleur RGB 0-255) par etat - couleurs choisies pour une
# lecture rapide par le jury : vert=repos, bleu=montee en pression,
# jaune=maintien, orange=relachement, rouge=urgence.
_ETAT_AFFICHAGE = {
    INACTIF:       ("INACTIF\nvanne ouverte", (0, 60, 0)),
    SERRAGE:       ("SERRAGE\npompe ON", (0, 0, 90)),
    DESSERRAGE:    ("DESSERRAGE\nvanne ouverte", (90, 40, 0)),
    STOP:          ("STOP\nmaintien press.", (90, 90, 0)),
    REGONFLAGE:    ("REGONFLAGE\npompe ON", (0, 60, 90)),
    ARRET_URGENCE: ("ARRET URGENCE\n(reset manuel)", (90, 0, 0)),
}


class LcdLink:
    """Meme interface que GantLink (serrer/desserrer/stop/regonfler/urgence/
    close), pour rester compatible avec keyword_actions.py sans le modifier
    autrement que l'import. Pas de connect() ni de PING ici : pas de liaison
    a maintenir, le LCD est ecrit en direct a chaque changement d'etat."""

    def __init__(self, bus=I2C_BUS):
        self._i2c = SMBus(bus)
        self._lock = threading.Lock()
        self._timer = None
        self._etat = None
        self._changer_etat(INACTIF, "demarrage")

    def _reg_lcd(self, reg, data):
        self._i2c.write_byte_data(LCD_ADDR, reg, data)

    def _reg_rgb(self, reg, data):
        self._i2c.write_byte_data(RGB_ADDR, reg, data)

    def _set_backlight(self, r, g, b):
        # Sequence d'init/ecriture du controleur RGB (PCA9633), reprise du
        # protocole standard du module Grove LCD RGB Backlight.
        self._reg_rgb(0x00, 0x00)
        self._reg_rgb(0x01, 0x00)
        self._reg_rgb(0x08, 0xAA)
        self._reg_rgb(0x04, r)
        self._reg_rgb(0x03, g)
        self._reg_rgb(0x02, b)

    def _set_text(self, text):
        self._reg_lcd(0x80, 0x01)         # clear display
        time.sleep(0.05)
        self._reg_lcd(0x80, 0x08 | 0x04)  # display on, curseur masque
        self._reg_lcd(0x80, 0x28)         # mode 2 lignes
        time.sleep(0.05)
        col = 0
        row = 0
        for c in text:
            if c == "\n" or col == 16:
                col = 0
                row += 1
                if row == 2:
                    break
                self._reg_lcd(0x80, 0xC0)  # curseur -> debut de la 2e ligne
                if c == "\n":
                    continue
            col += 1
            self._reg_lcd(0x40, ord(c))

    def _appliquer_etat(self, etat):
        texte, couleur = _ETAT_AFFICHAGE[etat]
        self._set_text(texte)
        self._set_backlight(*couleur)

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
        self._changer_etat(ARRET_URGENCE, "commande vocale URGENCE")

    def close(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
        try:
            self._set_text("")
            self._set_backlight(0, 0, 0)
        finally:
            self._i2c.close()
