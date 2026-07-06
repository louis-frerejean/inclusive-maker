#!/usr/bin/env python3
"""Reconnaissance vocale hors ligne (Vosk) en continu depuis le microphone."""
import argparse
import json
import queue
import sys
from datetime import datetime
from pathlib import Path

import sounddevice as sd
from vosk import KaldiRecognizer, Model, SetLogLevel

from keyword_actions import check_keywords, vosk_grammar

SetLogLevel(-1)

DEFAULT_MODEL_DIR = Path(__file__).parent / "models" / "vosk-model-small-fr-0.22"
DEFAULT_LOG_FILE = Path(__file__).parent / "logs" / "transcription.log"

audio_queue = queue.Queue()


def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"Avertissement audio: {status}", file=sys.stderr)
    audio_queue.put(bytes(indata))


def log_transcription(log_path, text):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {text}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Reconnaissance vocale hors ligne (Vosk) pour Raspberry Pi"
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_DIR,
                         help="Chemin vers le modele Vosk")
    parser.add_argument("--device", type=int, default=None,
                         help="Index du peripherique audio d'entree (voir --list-devices)")
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE,
                         help="Fichier de log des transcriptions")
    parser.add_argument("--list-devices", action="store_true",
                         help="Lister les peripheriques audio disponibles et quitter")
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    if not args.model.exists():
        sys.exit(
            f"Modele introuvable: {args.model}\n"
            "Executez install.sh pour le telecharger, ou passez --model."
        )

    device_info = sd.query_devices(args.device, "input")
    samplerate = int(device_info["default_samplerate"])

    model = Model(str(args.model))
    # Grammaire contrainte : Vosk ne peut reconnaitre que le mot declencheur,
    # "ouvrir"/"fermer", ou "[unk]" pour tout le reste. Reduit les confusions
    # par rapport a une reconnaissance libre sur tout le vocabulaire francais.
    recognizer = KaldiRecognizer(model, samplerate, json.dumps(vosk_grammar()))

    print("Ecoute en cours... (Ctrl+C pour arreter)")

    try:
        with sd.RawInputStream(
            samplerate=samplerate,
            blocksize=samplerate // 2,
            device=args.device,
            dtype="int16",
            channels=1,
            callback=audio_callback,
        ):
            while True:
                data = audio_queue.get()
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        print(f"> {text}")
                        log_transcription(args.log_file, text)
                        check_keywords(text)
    except KeyboardInterrupt:
        print("\nArret de la reconnaissance vocale.")
    except Exception as e:
        sys.exit(f"Erreur: {e}")


if __name__ == "__main__":
    main()
