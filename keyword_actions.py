"""Detection de mots-cles et envoi de la commande au gant (Fork 1 - Inclusiv'Maker).

Cible reelle : Raspberry Pi -> Bluetooth -> ESP32 (gere par Cecile : hardware et
firmware de la pompe/du gant) -> pompe -> gant. Tant que l'ESP32 n'est pas
disponible/appaire, on retombe sur la LED ACT du Pi comme simulation locale, utile
pour tester la reconnaissance vocale seule.

Definir la variable d'environnement GANT_BT_MAC (adresse MAC Bluetooth de l'ESP32)
pour activer l'envoi reel des commandes.
"""
import os
import unicodedata
from pathlib import Path

from gant_link import GantLink

LED_BRIGHTNESS_FILE = Path("/sys/class/leds/ACT/brightness")

OPEN_KEYWORDS = ("ouvrir", "ouvre")
CLOSE_KEYWORDS = ("fermer", "ferme")

_gant_mac = os.environ.get("GANT_BT_MAC")
_gant_link = None

if _gant_mac:
    _gant_link = GantLink(_gant_mac)
    _gant_link.connect()


def open_glove():
    if _gant_link:
        _gant_link.open_glove()
    else:
        # Cette LED est inversee: 0 = allumee, 1 = eteinte.
        LED_BRIGHTNESS_FILE.write_text("0")
        print("[SIMULATION] LED ACT allumee (ouvrir)")


def close_glove():
    if _gant_link:
        _gant_link.close_glove()
    else:
        LED_BRIGHTNESS_FILE.write_text("1")
        print("[SIMULATION] LED ACT eteinte (fermer)")


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def check_keywords(text):
    normalized = strip_accents(text.lower())
    if any(keyword in normalized for keyword in OPEN_KEYWORDS):
        open_glove()
    elif any(keyword in normalized for keyword in CLOSE_KEYWORDS):
        close_glove()
