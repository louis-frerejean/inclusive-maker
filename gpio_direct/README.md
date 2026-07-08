# Inclusive Maker - Version experimentale (GPIO direct, Pi 5)

**Statut : exploration, pas utilisee pour la soutenance du 2026-07-09.** La
version qui sert de reference est [`../bluetooth_esp32/`](../bluetooth_esp32/)
(Pi -> Bluetooth -> ESP32 -> pompe, deja testee).

## Idee

Le Pi 5 recu a une carte d'extension GPIO (actuellement sur breadboard). Au
lieu de faire transiter les commandes par Bluetooth vers un ESP32 qui pilote
lui-meme la pompe/vanne, cette variante fait piloter les relais pompe/vanne
**directement par les GPIO du Pi** - `gpio_link.py` reprend la machine a
etats du firmware ESP32 de Cecile (`Pomp_control_v3.ino`) mais l'execute cote
Pi en Python.

`voice_recognition.py` est une copie inchangee de la version Bluetooth (rien
la dedans n'est specifique au transport). `keyword_actions.py` est adapte
pour importer `GpioLink` au lieu de `GantLink`.

## Ce qui manque avant de brancher une vraie pompe

- **Cablage non verifie** : `POMPE_PIN`/`VANNE_PIN` dans `gpio_link.py` sont
  des numeros BCM par defaut (17/27), pas encore confirmes contre le cablage
  reel de la carte d'extension + breadboard. A adapter via les variables
  d'environnement `GANT_GPIO_POMPE_PIN` / `GANT_GPIO_VANNE_PIN`.
- **Polarite des relais** (`active_high=False` suppose un relais actif bas,
  comme sur l'ESP32) a verifier sur le module reellement utilise.
- **Perte du fail-safe materiel** : sur l'ESP32, une carte separee coupe la
  pompe automatiquement si la liaison avec le Pi tombe (watchdog PING,
  independant d'un plantage du Pi). Ici, si le Pi gele ou plante, plus rien
  ne coupe les relais tout seul. A ne pas utiliser sur la pompe reelle sans
  watchdog materiel independant.
- **Jamais teste avec une pompe/vanne reelles.**

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

## Tester la machine a etats sans relais branches

`GANT_GPIO_DISABLE=1 python voice_recognition.py --model ...` retombe sur la
simulation LED ACT (comme la version Bluetooth quand `GANT_BT_MAC` n'est pas
defini), pour valider la reconnaissance vocale seule.
