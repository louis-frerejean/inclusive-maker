# Inclusive Maker - Fork 1 (commande vocale)

Pipeline reconnaissance vocale -> pilotage pompe/gant, sans ESP32 : le Pi 5
pilote directement en GPIO un ecran QAPASS LCD1602 (affichage texte) et la
vraie pompe/vanne (module relais + bouton poussoir fournis par Cecile), en
parallele. Voir [`gpio_direct/`](gpio_direct/) pour le code, le cablage et
les consignes de securite avant de brancher la pompe.

Une version anterieure passait par un ESP32 intermediaire en Bluetooth
(architecture initialement prevue au cahier des charges) ; elle a ete
retiree du depot une fois `gpio_direct/` valide et retenu pour la
soutenance - voir l'historique git si besoin de la retrouver.

Contexte projet complet, cahier des charges, interviews : [`docs/CONTEXTE_PROJET.md`](docs/CONTEXTE_PROJET.md).
