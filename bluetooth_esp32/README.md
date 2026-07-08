# Inclusive Maker - Reconnaissance vocale (Raspberry Pi)

Reconnaissance vocale hors ligne en francais, basee sur [Vosk](https://alphacephei.com/vosk/), pour Raspberry Pi. Transcrit la parole du microphone en continu et enregistre le texte reconnu dans un fichier de log.

## Materiel requis

- Raspberry Pi (3, 4 ou 5 recommande) sous Raspberry Pi OS
- Microphone USB (recommande) ou carte son avec entree micro

## Installation

1. Copier ce dossier sur le Raspberry Pi.
2. Rendre le script d'installation executable et le lancer :

   ```bash
   chmod +x install.sh
   ./install.sh
   ```

   Ce script installe les dependances systeme, cree un environnement virtuel Python, installe `vosk` et `sounddevice`, et telecharge le modele francais `vosk-model-small-fr-0.22` (~40 Mo) dans `models/`.

## Verifier le microphone

Lister les peripheriques audio disponibles :

```bash
source venv/bin/activate
python voice_recognition.py --list-devices
```

Repérer l'index du microphone dans la colonne de gauche (ex: `1 USB Audio Device`).

## Lancer la reconnaissance vocale

```bash
source venv/bin/activate
python voice_recognition.py --device 1
```

(Omettre `--device` pour utiliser le peripherique par defaut du systeme.)

Le texte reconnu s'affiche dans le terminal et est enregistre avec horodatage dans `logs/transcription.log`.

Arreter avec `Ctrl+C`.

## Options disponibles

| Option | Description | Defaut |
|---|---|---|
| `--model` | Chemin vers le modele Vosk | `models/vosk-model-small-fr-0.22` |
| `--device` | Index du peripherique audio d'entree | peripherique par defaut |
| `--log-file` | Fichier de log des transcriptions | `logs/transcription.log` |
| `--list-devices` | Liste les peripheriques audio et quitte | - |

## Aller plus loin

- Modele plus precis mais plus lourd : `vosk-model-fr-0.22` (~1.5 Go) sur https://alphacephei.com/vosk/models
- Pour declencher des actions (GPIO, domotique, etc.) a partir des mots reconnus, brancher la logique metier sur le texte recupere dans `voice_recognition.py` (variable `text` dans la boucle principale).
