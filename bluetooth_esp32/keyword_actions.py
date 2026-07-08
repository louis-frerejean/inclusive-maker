"""Detection de mots-cles et envoi de la commande au gant (Fork 1 - Inclusiv'Maker).

Cible reelle : Raspberry Pi -> Bluetooth -> ESP32 (gere par Cecile : hardware et
firmware de la pompe/du gant) -> pompe -> gant. Tant que l'ESP32 n'est pas
disponible/appaire, on retombe sur la LED ACT du Pi comme simulation locale, utile
pour tester la reconnaissance vocale seule.

Definir la variable d'environnement GANT_BT_MAC (adresse MAC Bluetooth de l'ESP32)
pour activer l'envoi reel des commandes.

Etats de la pompe (voir arduino/Pomp_control_V3) : INACTIF, SERRAGE, DESSERRAGE,
STOP, REGONFLAGE, ARRET_URGENCE. Mots-ordres vocaux : "fermer" (declenche
SERRAGE), "ouvrir" (declenche DESSERRAGE), "stop", "regonfler", "help" (declenche
ARRET_URGENCE). ("serrer"/"desserrer" abandonnes: meme racine, se confondaient a
la reconnaissance. "urgence" abandonne au profit de "help": mal interprete par
Vosk.)

Fonctionnement mot declencheur (comme "dites Siri" puis la demande) : il faut
d'abord dire le mot magique (par defaut "wake up", surchargeable via la variable
d'environnement GANT_WAKE_WORD), ce qui ouvre une fenetre d'ecoute de
LISTEN_WINDOW_S secondes pendant laquelle "fermer"/"ouvrir"/"stop"/"regonfler"/
"help" sont pris en compte (tous, y compris "help", qui necessite "wake up"
avant comme les autres). Des qu'un premier ordre valide est donne, la fenetre
est prolongee a
EXTEND_WINDOW_S secondes (plus large que la fenetre initiale), pour pouvoir
enchainer plusieurs ordres sans redire le mot declencheur a chaque fois. Sans
mot declencheur, ou apres expiration de la fenetre, ces mots dits en
conversation normale sont ignores (evite les faux declenchements). La fonction
vosk_grammar() restreint en plus le vocabulaire que Vosk peut reconnaitre a ces
mots-la (+ "[unk]" pour le reste), pour eviter les confusions phonetiques avec
d'autres mots du francais.

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
# "fermer"/"ouvrir": paire d'antonymes naturelle, deja validee sur ce Pi/modele
# (2026-07-06), et sans aucun risque de collision entre eux (contrairement a
# "serrer"/"desserrer", qui partagent la meme racine et se confondaient).
SERRER_KEYWORDS = ("fermer",)
DESSERRER_KEYWORDS = ("ouvrir",)
STOP_KEYWORDS = ("stop",)
REGONFLER_KEYWORDS = ("regonfler",)
# "help" plutot que "urgence": "urgence" etait mal interprete par Vosk (meme
# type de souci que le choix initial de "wake up" en anglais - mot simple,
# distinct phonetiquement des autres mots-ordres francais).
URGENCE_KEYWORDS = ("help",)

LISTEN_WINDOW_S = 5.0   # fenetre initiale apres le mot declencheur
EXTEND_WINDOW_S = 10.0  # fenetre apres un premier ordre valide (plus large,
                        # pour enchainer plusieurs ordres sans redire "wake up")


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
    try:
        _gant_link = GantLink(_gant_mac)
        _gant_link.connect()
    except OSError as e:
        print(f"[BT] Connexion a l'ESP32 impossible ({e}) - retour en simulation LED")
        _gant_link = None

_state_lock = threading.Lock()
_unlocked_until = 0.0
_relock_timer = None


def _relock():
    global _unlocked_until
    with _state_lock:
        _unlocked_until = 0.0
    print("[MOT DECLENCHEUR] Fenetre expiree, reverrouille.")


def _open_window(duration_s, message=None):
    """(Re)ouvre la fenetre d'ecoute pour duration_s secondes."""
    global _unlocked_until, _relock_timer
    with _state_lock:
        _unlocked_until = time.monotonic() + duration_s
        if _relock_timer:
            _relock_timer.cancel()
        _relock_timer = threading.Timer(duration_s, _relock)
        _relock_timer.daemon = True
        _relock_timer.start()
    if message:
        print(message)


def _unlock():
    _open_window(LISTEN_WINDOW_S, "[MOT DECLENCHEUR] Detecte, en ecoute pour 5s...")


def _extend_window():
    """Prolonge la fenetre apres un ordre valide, pour enchainer sans redire le
    mot declencheur (ex: "serrer" puis "regonfler" quelques secondes plus tard).
    Fenetre plus large (EXTEND_WINDOW_S) qu'au premier declenchement, pour
    laisser plus de temps une fois qu'un premier ordre a ete donne. Pas de log
    ici: l'action elle-meme (ex: "[ACTION] ... SERRER") suffit comme signal."""
    _open_window(EXTEND_WINDOW_S)


def _close_window():
    """Ferme la fenetre d'ecoute immediatement (utilise pour "urgence")."""
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


def _matches(normalized, keywords):
    """Vrai si un des mots-cles apparait comme mot(s) entier(s) dans le texte.

    Match par mot exact plutot que par sous-chaine: "serrer" ne doit pas
    matcher dans "desserrer" (piege classique des sous-chaines en francais,
    avec les prefixes comme "de-"/"re-").
    """
    words = normalized.split()
    for keyword in keywords:
        keyword_words = keyword.split()
        n = len(keyword_words)
        if any(words[i:i + n] == keyword_words for i in range(len(words) - n + 1)):
            return True
    return False


def check_keywords(text):
    normalized = strip_accents(text.lower())

    with _state_lock:
        is_unlocked = time.monotonic() < _unlocked_until

    if not is_unlocked:
        if _matches(normalized, WAKE_KEYWORDS):
            _unlock()
        return

    if _matches(normalized, URGENCE_KEYWORDS):
        _close_window()
        urgence()
    elif _matches(normalized, SERRER_KEYWORDS):
        _extend_window()
        serrer()
    elif _matches(normalized, DESSERRER_KEYWORDS):
        _extend_window()
        desserrer()
    elif _matches(normalized, STOP_KEYWORDS):
        _extend_window()
        stop()
    elif _matches(normalized, REGONFLER_KEYWORDS):
        _extend_window()
        regonfler()
