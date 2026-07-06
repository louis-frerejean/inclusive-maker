"""Detection de mots-cles et envoi de la commande au gant (Fork 1 - Inclusiv'Maker).

Cible reelle : Raspberry Pi -> Bluetooth -> ESP32 (gere par Cecile : hardware et
firmware de la pompe/du gant) -> pompe -> gant. Tant que l'ESP32 n'est pas
disponible/appaire, on retombe sur la LED ACT du Pi comme simulation locale, utile
pour tester la reconnaissance vocale seule.

Definir la variable d'environnement GANT_BT_MAC (adresse MAC Bluetooth de l'ESP32)
pour activer l'envoi reel des commandes.

Etats de la pompe (voir arduino/Pomp_control_V3) : INACTIF, SERRAGE, DESSERRAGE,
STOP, REGONFLAGE, ARRET_URGENCE. Mots-ordres vocaux : "serrer", "desserrer",
"stop", "regonfler", "urgence".

Fonctionnement mot declencheur (comme "dites Siri" puis la demande) : il faut
d'abord dire le mot magique (par defaut "wake up", surchargeable via la variable
d'environnement GANT_WAKE_WORD), ce qui ouvre une fenetre d'ecoute de quelques
secondes pendant laquelle "serrer"/"desserrer"/"stop"/"regonfler" sont pris en
compte. Sans mot declencheur, ou apres expiration de la fenetre, ces mots dits en
conversation normale sont ignores (evite les faux declenchements). La fonction
vosk_grammar() restreint en plus le vocabulaire que Vosk peut reconnaitre a ces
mots-la (+ "[unk]" pour le reste), pour eviter les confusions phonetiques avec
d'autres mots du francais.

"urgence" est une exception volontaire : reconnu a tout moment, meme hors de la
fenetre d'ecoute, pour ne pas ajouter de delai (dire "wake up" d'abord) avant un
arret d'urgence reel.

Pas de retour sonore (bip) pour l'instant: a faire plus tard (le Pi n'a pas de
sortie audio par defaut configuree). Voir docs/CONTEXTE_PROJET.md, section "A
faire".
"""
import os
import threading
import time
import unicodedata
from pathlib import Path

from gant_link import GantLink

LED_BRIGHTNESS_FILE = Path("/sys/class/leds/ACT/brightness")

# "wake up": simple a prononcer, peu de risque qu'un tiers le dise par hasard
# pres de l'utilisateur sur une plage francophone. Teste sur le Pi (2026-07-06) :
# bien reconnu malgre le modele Vosk francais.
WAKE_KEYWORDS = (os.environ.get("GANT_WAKE_WORD", "wake up"),)
SERRER_KEYWORDS = ("serrer",)
DESSERRER_KEYWORDS = ("desserrer",)
STOP_KEYWORDS = ("stop",)
REGONFLER_KEYWORDS = ("regonfler",)
URGENCE_KEYWORDS = ("urgence",)

LISTEN_WINDOW_S = 5.0


def vosk_grammar():
    """Vocabulaire auquel Vosk doit se limiter (voir voice_recognition.py).

    Contraindre la reconnaissance a cette liste (mot declencheur + commandes +
    "[unk]" pour le reste) evite que Vosk ne confonde un mot-ordre avec un
    autre mot du francais: en dehors de cette liste, tout est reconnu comme
    "[unk]" plutot que comme un mot proche phonetiquement.
    """
    return (
        list(WAKE_KEYWORDS)
        + list(SERRER_KEYWORDS)
        + list(DESSERRER_KEYWORDS)
        + list(STOP_KEYWORDS)
        + list(REGONFLER_KEYWORDS)
        + list(URGENCE_KEYWORDS)
        + ["[unk]"]
    )

_gant_mac = os.environ.get("GANT_BT_MAC")
_gant_link = None

if _gant_mac:
    _gant_link = GantLink(_gant_mac)
    _gant_link.connect()

_state_lock = threading.Lock()
_unlocked_until = 0.0
_relock_timer = None


def _relock():
    global _unlocked_until
    with _state_lock:
        _unlocked_until = 0.0
    print("[MOT DECLENCHEUR] Fenetre expiree, reverrouille.")


def _unlock():
    global _unlocked_until, _relock_timer
    with _state_lock:
        _unlocked_until = time.monotonic() + LISTEN_WINDOW_S
        if _relock_timer:
            _relock_timer.cancel()
        _relock_timer = threading.Timer(LISTEN_WINDOW_S, _relock)
        _relock_timer.daemon = True
        _relock_timer.start()
    print("[MOT DECLENCHEUR] Detecte, en ecoute pour 5s...")


def _consume_window():
    """Ferme la fenetre d'ecoute immediatement apres une commande valide."""
    global _unlocked_until, _relock_timer
    with _state_lock:
        _unlocked_until = 0.0
        if _relock_timer:
            _relock_timer.cancel()
            _relock_timer = None


def serrer():
    if _gant_link:
        _gant_link.serrer()
    else:
        # Cette LED est inversee: 0 = allumee, 1 = eteinte.
        LED_BRIGHTNESS_FILE.write_text("0")
        print("[SIMULATION] LED ACT allumee (serrer)")


def desserrer():
    if _gant_link:
        _gant_link.desserrer()
    else:
        LED_BRIGHTNESS_FILE.write_text("1")
        print("[SIMULATION] LED ACT eteinte (desserrer)")


def stop():
    if _gant_link:
        _gant_link.stop()
    else:
        print("[SIMULATION] stop (maintien de l'etat actuel)")


def regonfler():
    if _gant_link:
        _gant_link.regonfler()
    else:
        print("[SIMULATION] regonfler (recharge courte)")


def urgence():
    if _gant_link:
        _gant_link.urgence()
    else:
        print("[SIMULATION] URGENCE declenchee")


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def check_keywords(text):
    normalized = strip_accents(text.lower())

    # "urgence" contourne volontairement la fenetre du mot declencheur :
    # une vraie urgence ne doit pas attendre "wake up" d'abord.
    if any(keyword in normalized for keyword in URGENCE_KEYWORDS):
        _consume_window()
        urgence()
        return

    with _state_lock:
        is_unlocked = time.monotonic() < _unlocked_until

    if not is_unlocked:
        if any(keyword in normalized for keyword in WAKE_KEYWORDS):
            _unlock()
        return

    if any(keyword in normalized for keyword in SERRER_KEYWORDS):
        _consume_window()
        serrer()
    elif any(keyword in normalized for keyword in DESSERRER_KEYWORDS):
        _consume_window()
        desserrer()
    elif any(keyword in normalized for keyword in STOP_KEYWORDS):
        _consume_window()
        stop()
    elif any(keyword in normalized for keyword in REGONFLER_KEYWORDS):
        _consume_window()
        regonfler()
