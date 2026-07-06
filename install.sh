#!/usr/bin/env bash
# Installation sur Raspberry Pi (Raspberry Pi OS / Debian).
set -e

echo "Installation des dependances systeme..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libportaudio2 unzip wget

echo "Creation de l'environnement virtuel..."
python3 -m venv venv
source venv/bin/activate

echo "Installation des dependances Python..."
pip install --upgrade pip
pip install -r requirements.txt

MODEL_DIR="models"
MODEL_NAME="vosk-model-small-fr-0.22"
MODEL_ZIP="$MODEL_NAME.zip"
MODEL_URL="https://alphacephei.com/vosk/models/$MODEL_ZIP"

if [ ! -d "$MODEL_DIR/$MODEL_NAME" ]; then
    echo "Telechargement du modele francais Vosk ($MODEL_NAME)..."
    mkdir -p "$MODEL_DIR"
    wget -O "/tmp/$MODEL_ZIP" "$MODEL_URL"
    unzip "/tmp/$MODEL_ZIP" -d "$MODEL_DIR"
    rm "/tmp/$MODEL_ZIP"
else
    echo "Modele deja present, telechargement ignore."
fi

echo ""
echo "Installation terminee."
echo "Activez l'environnement avec: source venv/bin/activate"
echo "Verifiez votre micro avec: python voice_recognition.py --list-devices"
echo "Lancez la reconnaissance avec: python voice_recognition.py"
