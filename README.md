# Inclusive Maker - Fork 1 (commande vocale)

Deux versions du pipeline reconnaissance vocale -> pilotage pompe/gant :

- [`bluetooth_esp32/`](bluetooth_esp32/) - version avec ESP32 intermediaire
  (Pi -> Bluetooth -> ESP32 -> pompe/gant), non utilisee pour la soutenance
  finale.
- [`gpio_direct/`](gpio_direct/) - **version utilisee pour la soutenance
  (2026-07-09)**. Pi -> GPIO direct, sans ESP32 : pilote a la fois un ecran
  QAPASS LCD1602 (affichage texte) et la vraie pompe/vanne (module relais +
  bouton poussoir fournis par Cecile), en parallele - voir le README de ce
  dossier pour les consignes de securite avant de brancher la pompe.

Contexte projet complet, cahier des charges, interviews : [`docs/CONTEXTE_PROJET.md`](docs/CONTEXTE_PROJET.md).
