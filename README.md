# Inclusive Maker - Fork 1 (commande vocale)

Deux versions du pipeline reconnaissance vocale -> pilotage pompe/gant :

- [`bluetooth_esp32/`](bluetooth_esp32/) - **version de reference**, utilisee
  pour la soutenance (2026-07-09). Pi -> Bluetooth -> ESP32 (firmware/hardware
  pompe geres par Cecile) -> pompe/gant.
- [`gpio_direct/`](gpio_direct/) - **experimentale**, pas utilisee pour la
  soutenance. Pi -> GPIO direct (carte d'extension sur breadboard) -> relais
  pompe/vanne, sans ESP32 intermediaire. Voir le README de ce dossier pour ce
  qui manque avant de brancher une vraie pompe.

Contexte projet complet, cahier des charges, interviews : [`docs/CONTEXTE_PROJET.md`](docs/CONTEXTE_PROJET.md).
