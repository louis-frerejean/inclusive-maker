# Inclusive Maker - Version demo (QAPASS LCD1602 + pompe reelle, Pi 5)

**Version utilisee pour la soutenance du 2026-07-09.** Pas d'ESP32 : le Pi
pilote directement en GPIO a la fois un ecran **QAPASS LCD1602** (affichage
texte) et la **vraie pompe/vanne** (module relais 2 canaux + bouton
poussoir, fournis par Cecile), en parallele. Le visuel web de Clemence
(`../dashboard/visuel-gants.html`) est aussi mis a jour a chaque commande
via `hand_visual_state.py` (voir ci-dessous).

(Une version anterieure passait par un ESP32 en Bluetooth - retiree du
depot une fois cette version validee ; voir l'historique git si besoin.)

## ATTENTION SECURITE - a lire avant de brancher la pompe

Le gant sera reellement porte pendant la demo. Sur l'ESP32, le bouton
poussoir etait un fail-safe **materiel independant** du Pi (meme si le Pi
plantait, l'ESP32 continuait de fonctionner). Ici, le bouton est lu par le
**meme processus Python** que la reconnaissance vocale : si ce processus se
bloque ou plante pendant que la pompe est active, ni la coupure
automatique par duree, ni le bouton ne fonctionnent plus. **A verifier avec
Cecile si un coupe-circuit materiel independant du Pi est possible en
complement** (ex: cable directement dans l'alimentation du relais).

**Avant de porter le gant pour la premiere fois :**
1. Teste tout le pipeline (mot declencheur + toutes les commandes + bouton) **sans que personne ne porte le gant**, en observant juste les clics de relais / le LCD / le visuel web.
2. Verifie que le bouton poussoir force bien `ARRET_URGENCE` immediatement, et qu'un second appui revient bien a `INACTIF`.
3. Verifie que les durees automatiques (8s gonflage, 5s desserrage, 2s regonflage) correspondent a ce qui est attendu avant de faire confiance au systeme avec une main dedans.

## Historique

Un premier module d'ecran (Grove LCD RGB Backlight v4.0) avait ete teste
avant le QAPASS mais s'est revele defectueux (ligne SCL bloquee a l'etat
bas quel que soit le cablage, confirme le 2026-07-08) - voir l'historique
dans `lcd_link.py`.

## Cablage

**Ecran QAPASS LCD1602**, relie au bus I2C du Pi 5 :

| LCD1602 | Pi 5 |
|---|---|
| GND | GND |
| VCC | **3.3V** (pas 5V - le Pi n'est pas tolerant 5V sur ses GPIO) |
| SDA | GPIO2 (SDA1) |
| SCL | GPIO3 (SCL1) |

**Module relais pompe/vanne + bouton poussoir** (fourni par Cecile), broches
par defaut (voir `pump_link.py`, surchargeables via `GANT_GPIO_POMPE_PIN` /
`GANT_GPIO_VANNE_PIN` / `GANT_GPIO_BOUTON_PIN`) :

| Fil | Pi 5 (BCM par defaut) |
|---|---|
| 5V | 5V (alimentation du module relais, PAS un GPIO de signal) |
| GND | GND |
| Pompe | GPIO17 |
| Valve | GPIO27 |
| Bouton | GPIO22 |

Avant de lancer quoi que ce soit :

1. Activer l'I2C : `sudo raspi-config` -> *Interface Options* -> *I2C* -> activer.
2. Verifier que le LCD est vu : `sudo i2cdetect -y 1`. On doit voir apparaitre `27` (adresse par defaut du backpack PCF8574).
3. Si l'adresse detectee n'est pas `0x27` (cavaliers A0/A1/A2 soudes differemment), la surcharger : `export GANT_LCD_I2C_ADDR=0x3f` (ou l'adresse vue par `i2cdetect`) avant de lancer `voice_recognition.py`.
4. Si l'ecran s'allume mais que le texte est invisible/flou, ajuster le petit potentiometre bleu au dos du module (contraste).
5. Verifier la polarite du relais : le code suppose un relais actif bas (comme sur l'ESP32, `RELAIS_ON=LOW`) - si pompe/vanne s'activent a l'envers de ce qui est attendu, verifier le module fourni par Cecile.

## Installation

Le modele Vosk (`models/vosk-model-small-fr-0.22`, ~40 Mo) vit a la racine
du depot, partage avec le reste du projet :

```bash
cd gpio_direct
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python voice_recognition.py --model ../models/vosk-model-small-fr-0.22 --list-devices
```

## Lancement automatique au demarrage (systemd)

Pour que le Pi lance la reconnaissance vocale tout seul au boot, sans PC ni
SSH branche (autonomie, cf. ER3 du cahier des charges) :

```bash
sudo cp systemd/gant-vocal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gant-vocal.service
```

Suivre les logs en direct : `journalctl -u gant-vocal.service -f`. Le
service redemarre automatiquement en cas de plantage (`Restart=on-failure`)
- ca ne remplace pas un vrai fail-safe materiel (voir l'avertissement
securite plus haut), ca evite juste d'avoir a relancer le script a la main.

## Lancer le tableau de bord web

Le fichier `../dashboard/visuel-gants.html` lit `hand_state.json` (ecrit
par `hand_visual_state.py` a chaque commande) via `fetch()` - ca ne
fonctionne pas en ouvrant le fichier directement dans un navigateur
(`fetch()` est bloque sur `file://`), il faut un serveur HTTP :

```bash
cd ~/inclusive-maker   # racine du depot, pas gpio_direct/
python3 -m http.server 8000
```

Puis ouvrir `http://<IP_DU_PI>:8000/dashboard/visuel-gants.html` depuis un
navigateur sur le meme reseau.

## Tester sans LCD ni pompe branches

`GANT_LCD_DISABLE=1 GANT_PUMP_DISABLE=1 python voice_recognition.py --model ...`
retombe sur la simulation LED ACT, pour valider la reconnaissance vocale
seule. On peut aussi desactiver l'un ou l'autre independamment.

## A savoir

- `GANT_LCD_DISABLE` et `GANT_PUMP_DISABLE` desactivent chacun leur sortie
  independamment - utile pour tester une seule chose a la fois.
- Le bouton physique force `ARRET_URGENCE` depuis n'importe quel etat ; un
  second appui (en `ARRET_URGENCE`) reinitialise vers `INACTIF` - meme
  logique que le bouton sur l'ESP32.
