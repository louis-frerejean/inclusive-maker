# Contexte du projet — Inclusiv'Maker / Défi Handicap

## Le cadre

Projet mené à **L'École LDLC**, en partenariat avec l'association **AutonaBee**
("La ruche de l'autonomie"), intervenante : **Cécile Pacoret** (cecile.pacoret@autonabee.com).
C'est un module pédagogique "Défi Handicap" : des équipes d'élèves conçoivent des
interfaces homme-machine pour rendre l'autonomie à une personne en situation de handicap
réelle, sur un cycle préparation + sprint + soutenance devant jury.

Planning du sprint (2026) :
- 03/07 – 08/07 : prototypage (avec tests utilisateurs les 06 et 07/07)
- 09/07 9h-15h : présentations
- 09/07 15h : **showroom final avec jury**

## Le bénéficiaire : Philippe Oulevay

Philippe est **paralysé des deux mains** mais peut encore **bouger ses bras et parler**.
Il utilise déjà Siri et Google Home au quotidien. Il aime le sport en extérieur (kayak,
ski adapté, quad "Quadrix", **cerf-volant**). Il veut **reprendre le contrôle de ses mains**
pour ces activités.

Le projet global se décline en 4 "forks" (équipes), chacune explorant une modalité de
commande différente pour l'ouverture/fermeture d'un gant/orthèse :

| Fork | Modalité | Équipe |
|---|---|---|
| **Fork 1** | **Commande vocale** | **Clémence Loreau, Yelena Roy, Morgane Fromenteau, Louis Frerejean** |
| Fork 2 | Activation musculaire du bras (EMG, MyoWare) | Axel, Sofiane, Sacha, Robinson |
| Fork 3 | Activation musculaire du visage | Victor, Axel, Tristan |
| Fork 4 | Activation cérébrale (EEG/BCI) | Flavien, Aurélien, Tadeo |

Louis est dans **Fork 1 — Commande vocale**, avec un rôle de **développement logiciel
(Raspberry Pi & Arduino)**. Clémence gère le hardware, Morgane la gestion de projet/doc,
Yelena la communication/doc.

## Le vrai objectif technique (Fork 1)

Le scénario d'usage retenu : **Philippe fait du cerf-volant sur la plage** et doit pouvoir
**serrer/relâcher ses mains sur les poignées** sans les utiliser, via une **orthèse/gant
pneumatique** piloté à la voix.

Architecture validée dans le cahier des charges (rendu le 2 juillet) :
- **Raspberry Pi 5 (maître)** : capture audio (micro sans fil **Fulaim X5**, réduction de bruit),
  détection d'un **mot déclencheur ("wake word"**, ex. "Ok Orthèse"), reconnaissance vocale
  hors-ligne de l'ordre ("ouvrir" / "fermer"), conversion en un **ordre binaire simple (0/1)**.
- **Arduino (esclave)** : reçoit l'ordre binaire par liaison série/USB, pilote la puissance
  (relais/transistors) de la **pompe pneumatique** qui actionne l'orthèse. Intègre une
  **sécurité positive (fail-safe)** : watchdog "keep-alive" + bouton d'urgence physique — en
  cas de perte de signal, la pompe se coupe et une électrovanne décomprime pour rouvrir
  passivement les mains.

Séquence d'usage : mot déclencheur → fenêtre d'écoute active de 5s → ordre "ouvrir"/"fermer"
→ action pompe. Si rien n'est dit dans les 5s, le système se reverrouille (double bip).

### Ce qui est explicitement HORS PÉRIMÈTRE (cahier des charges déjà validé)

- **Pas de connexion Cloud** : système 100% autonome, aucune gestion réseau 4G/Wi-Fi
  prévue pour un usage sur la plage.
- Pas de synthèse vocale complexe (juste des bips, pour économiser les ressources du Pi).
- Pas d'aide à l'installation — un aidant valide est supposé présent pour équiper Philippe.

→ **Ceci tranche la question du passage à un service cloud (type Wit.ai) évoquée en
discussion : le CDC déjà rendu exclut cette option pour ce projet.** Le sujet reste
pertinent pour d'autres explorations personnelles, mais pas pour ce livrable-ci.

### Exigences clés du cahier des charges (matrice)

| Réf | Exigence | Critère | Valeur cible | Flexibilité |
|---|---|---|---|---|
| EF1 | Reconnaissance vocale | Taux de compréhension en milieu bruyant | > 90% | F0 (impératif) |
| EF2 | Sécurité positive | Temps de décompression de la pompe si coupure | < 500 ms | F0 (impératif) |
| ER1 | Robustesse matérielle | Protection contre le sable | IP54 min. | F1 (négociable) |
| ER2 | Poids embarqué | Masse totale sur l'utilisateur | < 1.5 kg | F1 (négociable) |
| ER3 | Autonomie | Fonctionnement continu sur batterie | 2h | F0 (impératif) |

Fonctions retenues à développer (3 max, argumentées) :
1. Reconnaissance du mot déclencheur + fin du déclenchement
2. Filtrage des mots pour éviter un déclenchement incessant
3. Bouton de sécurité pour arrêter pompe/machine (externe ou par l'utilisateur)
(+ pistes additionnelles : compatibilité 2 micros, noise cancelling logiciel pour que ça
marche même avec un sèche-mains en marche)

## Ce qu'on a appris de l'interview avec Philippe (notes brutes d'équipe)

- Tolérance aux erreurs : faible priorité pour lui, "il s'en tape" tant que ça marche globalement.
- Veut un retour d'info sur la **pression** (en PSI ou équivalent) plutôt qu'un son/vibration classique.
- En cas de panne : veut une **double sécurité**, mais **pas un lâcher complet** intempestif.
- Latence acceptable entre l'ordre et le mouvement du gant : **~2 secondes**, peu exigeant dessus.
- Utilise déjà couramment des commandes vocales (Siri, Google Home pour les lumières,
  ascenseur à commande vocale) — **veut que ce soit facilement modifiable/reconfigurable**.
- Parle français, un peu d'anglais (mots isolés, pas de phrases).
- Contexte sonore réel signalé **calme, pas de bruit de fond marqué même avec du vent**
  (nuance à garder en tête : l'hypothèse "plage très bruyante" est peut-être à relativiser
  par rapport à l'expérience réelle de l'utilisateur).
- Ne veut pas de distinction gauche/droite : le pilotage du cerf-volant en lui-même ne
  l'intéresse pas, seul le geste de serrer/relâcher compte.

## Suite du projet / liens externes

- **Trello** (suivi de tâches Fork 1) :
  https://trello.com/invite/b/6a451f5f803e95e6e375734c/ATTI4ea2d66af8df5458c0eb972c1566785236F266BA/fork-1-commande-vocale
- **Hackster.io** (documentation open-source à produire, exigée par le cadre pédagogique) :
  https://www.hackster.io/551074/2026-catch-all-fork-1-714765
- Ressources fournies par l'intervenante dans [Ressources mis a disposition par l'intervenante/](Ressources%20mis%20a%20disposition%20par%20l'intervenante/)
  (cahier des charges méthode, biais cognitifs, guides MyoWare pour Fork 2, interviews audio, etc.)

## Décision d'architecture : local vs cloud (2026-07-03)

**Décision : le pipeline reste 100% local (pas de cloud).** Ceci reconfirme, après
ré-évaluation, le choix déjà présent dans le cahier des charges rendu le 2 juillet
("Pas de connexion Cloud").

Contexte de la ré-évaluation : l'équipe s'est demandé si passer par un service cloud de
reconnaissance vocale (ex. Wit.ai) pour l'étape "ouvrir"/"fermer" (après le mot
déclencheur) améliorerait la précision par rapport à Vosk en local, notamment en
environnement venteux/bruyant.

Raisons de rester en local :
- Le vocabulaire à reconnaître est minuscule (1 mot déclencheur + "ouvrir"/"fermer"),
  un cas où un modèle local restreint (Vosk small avec grammaire limitée, ou un moteur
  de wake word dédié type Porcupine) peut déjà atteindre l'exigence EF1 (>90% en milieu
  bruyant) sans avoir besoin de la puissance d'un modèle cloud plus gros.
- Le cloud aurait ajouté une **dépendance réseau non prévue** (Wi-Fi/4G sur le site
  d'usage), un **nouveau composant matériel** (dongle 4G ou hotspot) qui grignote
  l'autonomie batterie (exigence ER3 : 2h), et un **nouveau mode de panne** (plus de
  commande vocale possible si le réseau tombe).
- Le fail-safe (EF2, <500ms) ne dépend de toute façon pas de l'endroit où tourne la
  reconnaissance vocale — c'est la liaison série Pi↔Arduino qui est critique, donc le
  cloud n'aurait de toute façon rien apporté à la sécurité.
- Gain de précision estimé marginal par rapport à la complexité ajoutée (timeout,
  repli automatique sur du local en cas de coupure réseau, gestion de deux chemins de
  code) pour un vocabulaire aussi restreint.

**Conséquence pratique :** l'énergie de dev se concentre sur Vosk local (mot déclencheur
+ reconnaissance "ouvrir"/"fermer") et sur la liaison série Pi → Arduino avec le
fail-safe, plutôt que sur une intégration cloud.

## Mise à jour matérielle — carte de contrôle des gants (mail Cécile, 2026-07-03)

La carte qui pilote la pompe/le gant n'est **pas un Arduino classique mais un ESP32**
(carte Elegoo) :
- Doc de référence : https://wiki.elegoo.com/en/Robots&Kits/preparation/first-look-esp32
- L'ESP32 a du **Wi-Fi et du Bluetooth natifs** → la liaison Pi ↔ carte peut se faire
  en Wi-Fi ou en Bluetooth (pas forcément filaire/série USB comme envisagé au départ) —
  **à l'équipe de choisir**, selon les mots de Cécile.
- Cécile pilotera la pompe via les broches **D5, D18, D19 et D21**.
- **Schéma électrique complet attendu lundi** (2026-07-06, jour de prototypage/tests
  utilisateurs du sprint).

Important : passer en Wi-Fi/Bluetooth entre le Pi et l'ESP32 est une liaison **locale
directe entre deux appareils** (pas un passage par Internet/cloud) — ça ne remet donc
pas en cause la décision "100% local, pas de cloud" prise plus haut, c'est un choix
de couche de transport différent, pas un changement de dépendance réseau externe.

**Décision (2026-07-03) : liaison Pi ↔ ESP32 en Bluetooth**, plutôt qu'en Wi-Fi/point
d'accès local. Raisons : aucune infrastructure réseau à configurer sur site, cohérent
avec l'esprit "100% autonome" déjà validé, faible consommation (important pour
l'exigence ER3, 2h d'autonomie), et le volume de données à transmettre est minuscule
(un simple ordre ouvrir/fermer) donc le débit limité du Bluetooth n'est pas un frein.

**Répartition des responsabilités (précision importante, 2026-07-03) : Cécile prend en
charge le hardware ET le firmware de la carte ESP32 (câblage de la pompe, du gant, et
le code qui pilote les broches D5/D18/D19/D21).** Ce n'est **pas** le travail du Fork 1.
Le rôle de l'équipe Fork 1 (Louis et son groupe) se limite strictement à : **reconnaître
la commande vocale sur le Raspberry Pi, et envoyer la bonne information à l'ESP32** via
la liaison choisie (Bluetooth). Écrire le firmware ESP32 n'est donc plus une tâche à
faire nous-mêmes — seul le protocole d'échange (quel texte/code envoyer, à quel moment)
doit être proposé et validé avec Cécile, puisqu'elle a dit "à vous de voir comment
interfacer".

## État du code (2026-07-06)

- `voice_recognition.py` + `keyword_actions.py` : reconnaissance vocale locale (Vosk)
  fonctionnelle, avec mot déclencheur ("wake up" par défaut, `GANT_WAKE_WORD` pour
  changer) ouvrant une fenêtre d'écoute de 5s, et grammaire Vosk contrainte
  (`vosk_grammar()`) pour limiter les confusions phonétiques. **Testé sur le Pi
  (2026-07-06) : "wake up" bien reconnu** malgré le modèle Vosk français
  (`vosk-model-small-fr-0.22`).
- `gant_link.py` : client Bluetooth (RFCOMM) côté Pi. Tant que l'ESP32 n'est pas
  défini (`GANT_BT_MAC` non renseignée), `keyword_actions.py` retombe sur la LED
  ACT du Pi comme simulation locale.
- **Machine à états redéfinie (2026-07-06)**, plus fine que la version initiale à 3
  états — voir `arduino/Pomp_control_V3/Pomp_control_v3/Pomp_control_v3.ino` :

  | État | Sortie | Déclenché par | Auto |
  |---|---|---|---|
  | INACTIF | pompe OFF, vanne ON | "desserrer" (après 8s), reset urgence | — |
  | SERRAGE | pompe ON, vanne OFF | "serrer" (depuis INACTIF/STOP) | → STOP après 8s (gonflage complet) |
  | DESSERRAGE | pompe OFF, vanne ON | "desserrer" (depuis STOP/SERRAGE) | → INACTIF après 8s |
  | STOP | pompe OFF, vanne OFF | "stop" (depuis SERRAGE/DESSERRAGE/REGONFLAGE) | — |
  | REGONFLAGE | pompe ON, vanne OFF | "regonfler" (depuis STOP uniquement) | → STOP après 2s |
  | ARRET_URGENCE | pompe OFF, vanne ON | bouton physique **ou** mot vocal "urgence" | — (reset manuel par bouton uniquement) |

  Mots-ordres vocaux : **"serrer"**, **"desserrer"**, **"stop"**, **"regonfler"**,
  **"urgence"** (+ "wake up" pour le mot déclencheur). "urgence" contourne
  volontairement la fenêtre d'écoute (reconnu à tout moment, pas de délai avant un
  arrêt d'urgence réel). Le bouton physique n'est plus le cycle générique d'origine :
  il est maintenant dédié à l'arrêt d'urgence (1er appui = urgence, 2e appui = reset
  vers INACTIF), correspondant à la fonction "bouton de sécurité" du cahier des
  charges. Durées : gonflage complet et désserrage = 8s chacun (désserrage repris par
  symétrie, pas de valeur donnée séparément — à confirmer), regonflage = 2s.
  Fail-safe perte liaison Bluetooth : retombe en INACTIF (pas ARRET_URGENCE, pour ne
  pas exiger de reset manuel à chaque micro-coupure).

  **Non encore testé sur le Pi/la vraie pompe** (contrairement à l'ancien modèle
  ouvrir/fermer à 3 états, qui lui a été validé bout-en-bout le 2026-07-06 avant
  cette refonte) — à retester avant la soutenance. **À confirmer avec Cécile** avant
  de reflasher : le mapping des états, les durées choisies, et le rôle du bouton
  physique redéfini en arrêt d'urgence.

## À faire

- **Retour sonore (bip) au déblocage/reverrouillage du mot déclencheur** : prévu
  par le cahier des charges ("juste des bips"), tenté le 2026-07-06 via
  `sounddevice`/`numpy` mais retiré du code — le Pi n'a pas de sortie audio par
  défaut configurée (`sd.play()` échoue avec "Error querying device -1"). À refaire
  une fois une sortie audio disponible/configurée sur le Pi (jack, USB, ou autre).

## Relation avec le POC précédent (voir RECAP.md)

Le POC "Vosk + LED ACT sur Raspberry Pi" documenté dans `RECAP.md` était un galop d'essai
personnel de reconnaissance vocale (avant que le cahier des charges officiel du Fork 1 ne
soit figé). Le **vrai livrable** est maintenant : Pi (wake word + STT hors-ligne, ordre
binaire) → liaison série → Arduino (pilotage pompe pneumatique + fail-safe), sans LED de
démo ni cloud. Les enseignements du POC (choix du modèle Vosk small, gestion du micro USB,
etc.) restent utiles mais la cible a évolué.
