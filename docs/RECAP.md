# Récap — POC reconnaissance vocale sur Raspberry Pi (Inclusive Maker)

Date : 2026-07-01

## Objectif

Construire un POC fonctionnel : un Raspberry Pi fait de la reconnaissance vocale hors ligne en français, et déclenche une action physique (allumer/éteindre) quand certains mots-clés sont prononcés.

## Matériel utilisé

- Raspberry Pi 5 (noyau `rpi-2712`), Raspberry Pi OS Lite 64-bit (Debian trixie)
- Kit de 4 micros-cravates sans fil avec récepteur, sortie **jack 3.5mm** (le port USB du récepteur ne sert qu'à charger, pas à transmettre l'audio)
- Adaptateur / carte son USB avec entrée jack (`Actions Semiconductor USB Audio & HID`) — indispensable car le Pi n'a pas d'entrée micro sur son propre jack 3.5mm (sortie uniquement)
- Une lampe DIY à base d'ESP32, utilisée dans un premier temps comme cible d'action puis abandonnée pour le POC (voir plus bas)
- PC Windows (HP Victus 15) utilisé comme relais réseau et terminal SSH

## Accès réseau / SSH au Pi

Pas d'écran ni de clavier/souris disponibles pour le Pi (pas d'accès HDMI possible depuis un PC portable, le port HDMI d'un PC est en sortie uniquement). Etapes suivies :

1. Carte SD reflashée avec **Raspberry Pi Imager**, configuration avancée : SSH activé (utilisateur/mot de passe), Wi-Fi renseigné.
2. Connexion physique **Ethernet direct** entre le Pi et le port RJ45 du PC.
3. **Partage de connexion Windows (ICS)** activé sur la carte Wi-Fi du PC, partagé vers la carte Ethernet — donne au Pi une IP dans `192.168.137.x` (le PC est `192.168.137.1`).
4. Recherche de l'IP du Pi via `arp -a` (les baux DHCP changent après chaque redémarrage du Pi, l'IP peut changer).
5. Connexion : `ssh <user>@192.168.137.X`

### Problèmes rencontrés et résolus
- **`kex_exchange_identification: read: Connection reset`** en boucle : résolu par un simple redémarrage du Pi (le service de génération des clés SSH n'avait pas terminé correctement au premier boot).
- Antivirus tiers (Kaspersky) suspecté puis écarté (pas la cause).
- Après chaque reboot, l'IP du Pi peut changer — toujours revérifier avec `arp -a`.

## Installation logicielle

Projet transféré sur le Pi via `scp` dans `~/inclusive-maker`. Fichiers :
- `install.sh` — installe les dépendances système (`libportaudio2`, etc.), crée un venv Python, installe `vosk` + `sounddevice`, télécharge le modèle Vosk français small.
- `requirements.txt` — `vosk`, `sounddevice`.
- `voice_recognition.py` — script principal.

### Correctifs apportés à `install.sh`
- `libatlas-base-dev` retiré : paquet obsolète sur Debian trixie (remplacé par OpenBLAS), et non nécessaire pour `vosk`/`sounddevice` de toute façon.

## Configuration audio

- Périphérique identifié via `python voice_recognition.py --list-devices` → index `0` (`USB Audio & HID`).
- Le script détecte automatiquement le taux d'échantillonnage natif du périphérique (`sd.query_devices(device, "input")["default_samplerate"]`) plutôt qu'un taux fixe — l'adaptateur USB ne supportait pas 16000 Hz nativement (utilise 48000 Hz). Vosk gère très bien un taux différent de 16 kHz en le déclarant au `KaldiRecognizer`.
- `blocksize` du flux audio rendu proportionnel au taux d'échantillonnage (`samplerate // 2`, ~500ms par bloc) plutôt que fixé en dur.

## Modèles Vosk testés

| Modèle | Taille | Résultat |
|---|---|---|
| `vosk-model-small-fr-0.22` | ~40 Mo | Rapide, temps réel garanti sur le Pi 5. Suffisant pour détecter des mots-clés courts ("allume"/"éteins"). **Retenu pour le POC.** |
| `vosk-model-fr-0.22` (complet, avec rescoring `rnnlm`) | ~1.4 Go | Bien plus précis sur des phrases complètes, mais sature un cœur CPU à 100% et utilise ~2.9 Go de RAM → latence croissante au fil du temps (le traitement n'arrive plus à suivre le flux audio en temps réel). Désactiver le dossier `rnnlm` n'a pas résolu la lenteur (le décodage du graphe complet est intrinsèquement lourd, pas seulement le rescoring). |

Pas de modèle français "moyen" officiel chez Vosk — seulement small et complet.

## Artefact de transcription observé (non bloquant)

En modèle complet notamment, certains mots affichaient une syllabe finale dupliquée ("fermée" → "ferméeée", "bonjour" → "bonjourur"). Diagnostic :
- Le fichier audio brut enregistré (`arecord`) est propre à l'écoute → ce n'est pas un problème micro/matériel.
- Transcrire ce même fichier en un seul bloc (non streamé) donne un résultat propre → ce n'est pas un problème de modèle en soi.
- Conclusion : artefact lié à la détection de fin de phrase (endpoint) en streaming, qui capture parfois la résonance/décroissance naturelle de la voix comme une syllabe en plus. Comportement connu et courant en ASR temps réel. **Accepté tel quel pour le POC** (n'affecte pas la détection des mots-clés courts comme "allume").

## Action physique déclenchée par mot-clé

Objectif initial : allumer une lampe branchée en USB. Plusieurs pistes explorées :

1. **Relais USB générique** : abandonné, pas de matériel disponible.
2. **Couper l'alimentation du port USB via `uhubctl`** : le Pi 5 annonce le support (`ppps` = per-port power switching) mais **couper le port ne coupe pas réellement le 5V physique** sur ce contrôleur — la lampe (ESP32 alimenté uniquement par USB) est restée allumée malgré le port signalé "off" côté logiciel. Limite matérielle connue sur certains contrôleurs USB.
3. **Commande série vers l'ESP32 de la lampe** : aurait nécessité de reprogrammer le firmware de l'ESP32 (non fait, pas le temps le jour du POC).
4. **Relais/MOSFET câblé sur un GPIO** : solution standard et fiable pour ce genre de projet Maker, mais aucun composant (relais, transistor, LED, résistance) disponible sur place.
5. **Solution retenue pour le POC** : la **LED ACT intégrée du Raspberry Pi** (`/sys/class/leds/ACT/`), pilotée directement en écriture dans le sysfs Linux, sans aucun câblage supplémentaire.

### Mise en œuvre de la LED ACT
```bash
echo none | sudo tee /sys/class/leds/ACT/trigger      # desactive le clignotement automatique (activite carte SD)
echo 0 | sudo tee /sys/class/leds/ACT/brightness       # test
echo 1 | sudo tee /sys/class/leds/ACT/brightness       # test
```
**Particularité constatée sur ce Pi** : la LED ACT est **inversée** — écrire `0` l'allume, écrire `1` l'éteint. Le code en tient compte (voir `relay_on()`/`relay_off()` dans `voice_recognition.py`).

Le script doit être lancé avec `sudo` (permissions nécessaires pour écrire dans `/sys/class/leds/`) :
```bash
sudo venv/bin/python voice_recognition.py --device 0
```
(chemin complet vers le python du venv, car `sudo` ne connaît pas l'environnement virtuel activé)

## Détection des mots-clés

Vosk transcrit parfois "éteins" avec des homophones différents selon la prononciation : "éteint", "étain", etc. Plutôt que de lister toutes les variantes une à une, la détection :
1. Retire les accents du texte reconnu (`unicodedata`)
2. Cherche le mot "allume" pour déclencher `relay_on()`
3. Cherche un préfixe `"etei"` ou `"etai"` pour déclencher `relay_off()` (couvre eteins/eteint/etain/etainte...)

## Etat actuel du dépôt

- `voice_recognition.py` — reconnaissance vocale + détection mots-clés + action LED ACT
- `install.sh` — installation automatisée sur Raspberry Pi
- `requirements.txt`
- `test_wav.py` — script de diagnostic (transcrit un fichier `.wav` en un seul bloc, utile pour isoler les problèmes streaming vs modèle)
- `README.md` — instructions d'installation/usage

## Prochaines étapes possibles

- Remplacer la LED ACT (démo) par une vraie action physique : relais/MOSFET câblé sur un GPIO, alimentation de la lampe en coupure (pas juste son port USB).
- Alternative : reprogrammer le firmware de la lampe ESP32 pour qu'elle écoute une commande série envoyée depuis le Pi (pas besoin de matériel supplémentaire, juste le câble USB déjà branché).
- Démarrage automatique du script au boot du Pi (service systemd).
- Étendre le vocabulaire de mots-clés / actions selon les besoins du produit final.
- Envisager `sudo` sans mot de passe (sudoers `NOPASSWD` limité à la commande nécessaire) si le script doit tourner de façon autonome sans intervention manuelle.
