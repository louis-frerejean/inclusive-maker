# Inclusive Maker - Fork 1 (commande vocale)

Deux versions du pipeline reconnaissance vocale -> pilotage pompe/gant :

- [`bluetooth_esp32/`](bluetooth_esp32/) - **version de reference**, utilisee
  pour la soutenance (2026-07-09). Pi -> Bluetooth -> ESP32 (firmware/hardware
  pompe geres par Cecile) -> pompe/gant.
- [`gpio_direct/`](gpio_direct/) - **version demo**, utilisee pour la
  soutenance (2026-07-09). Pi -> I2C direct -> ecran Grove LCD RGB Backlight
  v4.0 (sur breadboard), sans ESP32 ni pompe reelle : affiche l'ordre qui
  serait envoye a la pompe, pour simuler le comportement sans materiel
  pneumatique sur scene.

Contexte projet complet, cahier des charges, interviews : [`docs/CONTEXTE_PROJET.md`](docs/CONTEXTE_PROJET.md).
