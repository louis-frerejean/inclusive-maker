#!/usr/bin/env python3
"""Diagnostic: transcrit un fichier wav en un seul bloc (pas de streaming/chunking)."""
import sys
import wave
from pathlib import Path

from vosk import KaldiRecognizer, Model, SetLogLevel

SetLogLevel(-1)


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: python test_wav.py <fichier.wav> <dossier_modele>")

    wav_path = Path(sys.argv[1])
    model_path = Path(sys.argv[2])

    wf = wave.open(str(wav_path), "rb")
    print(f"Canaux: {wf.getnchannels()}, largeur: {wf.getsampwidth()}, taux: {wf.getframerate()} Hz")

    model = Model(str(model_path))
    recognizer = KaldiRecognizer(model, wf.getframerate())

    data = wf.readframes(wf.getnframes())
    recognizer.AcceptWaveform(data)
    print(recognizer.FinalResult())


if __name__ == "__main__":
    main()
