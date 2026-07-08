# Inclusive Maker - Version demo (Grove LCD RGB Backlight, Pi 5)

**Version utilisee pour la soutenance du 2026-07-09.** Contrairement a
[`../bluetooth_esp32/`](../bluetooth_esp32/) (Pi -> Bluetooth -> ESP32 ->
pompe reelle), aucune pompe ni ESP32 n'est branche pour la demo : seul un
ecran **Grove LCD RGB Backlight v4.0** est cable sur le breadboard, relie en
I2C au Pi 5. Il affiche l'ordre qui serait envoye a la pompe (texte +
couleur de retroeclairage), pour simuler visuellement le comportement sans
materiel pneumatique sur scene.

`voice_recognition.py` est une copie inchangee de la version Bluetooth (rien
la dedans n'est specifique au mode d'affichage). `keyword_actions.py` est
adapte pour importer `LcdLink` au lieu de `GantLink`. `lcd_link.py` reprend
la machine a etats du firmware ESP32 de Cecile (`Pomp_control_v3.ino`,
memes durees : gonflage 8s, desserrage 5s, regonflage 2s) mais l'affiche sur
le LCD au lieu de piloter des relais.

## Cablage

Grove LCD RGB Backlight v4.0 sur breadboard, relie au bus I2C du Pi 5 :

| Grove | Pi 5 |
|---|---|
| GND | GND |
| VCC | 5V |
| SDA | GPIO2 (SDA) |
| SCL | GPIO3 (SCL) |

Avant de lancer quoi que ce soit :

1. Activer l'I2C : `sudo raspi-config` -> *Interface Options* -> *I2C* -> activer, puis redemarrer.
2. Verifier que le module est vu : `sudo i2cdetect -y 1`. On doit voir apparaitre `3e` (texte) et `30` ou `62` (retroeclairage RGB selon la version - le v4.0 utilise normalement `0x30`, l'ancien v2.0 `0x62`).
3. Si l'adresse RGB detectee n'est pas `0x30`, la surcharger : `export GANT_LCD_RGB_ADDR=0x62` (ou l'adresse vue par `i2cdetect`) avant de lancer `voice_recognition.py`.

## Installation

Reutilise le meme modele Vosk que `bluetooth_esp32/` (inutile de re-telecharger
les ~40 Mo) :

```bash
cd gpio_direct
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python voice_recognition.py --model ../bluetooth_esp32/models/vosk-model-small-fr-0.22 --list-devices
```

## Tester sans le LCD branche

`GANT_LCD_DISABLE=1 python voice_recognition.py --model ...` retombe sur la
simulation LED ACT (comme la version Bluetooth quand `GANT_BT_MAC` n'est pas
defini), pour valider la reconnaissance vocale seule.

## A savoir

- Rien ici ne pilote de materiel pneumatique reel : c'est le mode le plus
  sur pour une demo live (pas de relais, pas d'actionneur).
- Comme pour la version Bluetooth, aucune commande de reset n'existe pour
  sortir de `ARRET_URGENCE` autrement qu'en relancant le script (le firmware
  ESP32 utilise un bouton physique pour ca, absent ici).
