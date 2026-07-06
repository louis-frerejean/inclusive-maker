/*
  ============================================================
  Projet      : Commande pompe + électrovanne
  Carte       : ESP32
  Auteur      : Cecile Pacoret (base) + Fork 1 (integration commande vocale BT)
  Date        : 06/07/2026
  Description :
    Commande vocale (Raspberry Pi -> Bluetooth, voir gant_link.py) :
      "SERRER"    -> depuis INACTIF ou STOP, lance SERRAGE (monte en
                     pression pendant DUREE_GONFLAGE, puis bascule seule en
                     STOP pour maintenir la prise sans forcer en continu)
      "DESSERRER" -> depuis STOP (ou en cours de SERRAGE), lance DESSERRAGE
                     (relache la pression pendant DUREE_DESSERRAGE, puis
                     bascule seule en INACTIF)
      "STOP"      -> depuis SERRAGE/DESSERRAGE/REGONFLAGE, fige pompe et
                     vanne immediatement, maintient la pression telle quelle
      "REGONFLER" -> depuis STOP uniquement, recharge courte (DUREE_REGONFLAGE)
                     sans repasser par un cycle de gonflage complet, puis
                     revient seule en STOP
      "URGENCE"   -> depuis n'importe quel etat, force ARRET_URGENCE
                     (equivalent au bouton physique, voir plus bas)
      "PING"      -> signal de vie de la liaison (voir fail-safe plus bas)

    États :
      INACTIF       : pompe OFF, vanne ON  (repos, aucune pression)
      SERRAGE       : pompe ON,  vanne OFF (monte en pression)
      DESSERRAGE    : pompe OFF, vanne ON  (relache la pression)
      STOP          : pompe OFF, vanne OFF (maintien de la pression actuelle)
      REGONFLAGE    : pompe ON,  vanne OFF (recharge courte depuis STOP)
      ARRET_URGENCE : pompe OFF, vanne ON  (securite, depressurisation totale)

    Sécurité :
      - Bouton physique (PIN_BOUTON) : dedie a l'arret d'urgence. Un appui
        force ARRET_URGENCE depuis n'importe quel etat ; un second appui
        realise le reset vers INACTIF (redemarrage manuel volontaire, on ne
        sort jamais de l'urgence tout seul).
      - Apres DUREE_GONFLAGE en SERRAGE, passage automatique en STOP.
      - Apres DUREE_DESSERRAGE en DESSERRAGE, passage automatique en INACTIF.
      - Apres DUREE_REGONFLAGE en REGONFLAGE, retour automatique en STOP.
      - Si plus aucun PING Bluetooth n'arrive pendant PING_TIMEOUT_MS alors
        que la liaison etait active, on force INACTIF (depressurisation) :
        fail-safe si le Raspberry Pi ou la liaison BT tombe. Choix distinct
        de ARRET_URGENCE pour ne pas exiger une intervention manuelle sur le
        bouton a chaque micro-coupure Bluetooth normale.
  ============================================================
*/

#include "BluetoothSerial.h"

BluetoothSerial SerialBT;
String bufferBT = "";

const unsigned long PING_TIMEOUT_MS = 3000;
unsigned long dernierPingRecu = 0;
bool liaisonBTActive = false;

// =========================
// Définition des broches
// =========================
#define PIN_POMPE     5
#define PIN_VANNE     18
#define PIN_BOUTON    21

// =========================
// Paramètres
// =========================
const int RELAIS_OFF  = HIGH;
const int RELAIS_ON = LOW;

const unsigned long DUREE_GONFLAGE    = 8000; // 8 secondes (gonflage complet)
const unsigned long DUREE_DESSERRAGE  = 8000; // 8 secondes (symetrique au gonflage, a ajuster si besoin)
const unsigned long DUREE_REGONFLAGE  = 2000; // 2 secondes (recharge courte)

// =========================
// États du système
// =========================
enum EtatSysteme {
  INACTIF,
  SERRAGE,
  DESSERRAGE,
  STOP,
  REGONFLAGE,
  ARRET_URGENCE
};

EtatSysteme etatSysteme = INACTIF;

// =========================
// Variables
// =========================
bool ancienEtatBouton = HIGH;
unsigned long tempsDebutEtat = 0;

// =========================
// Fonction : applique l'état
// =========================
void appliquerEtatSysteme() {
  tempsDebutEtat = millis();

  switch (etatSysteme) {

    case INACTIF:
      digitalWrite(PIN_POMPE, RELAIS_OFF);
      digitalWrite(PIN_VANNE, RELAIS_ON);
      Serial.println("ETAT INACTIF : pompe OFF, vanne ON");
      break;

    case SERRAGE:
      digitalWrite(PIN_POMPE, RELAIS_ON);
      digitalWrite(PIN_VANNE, RELAIS_OFF);
      Serial.println("ETAT SERRAGE : pompe ON, vanne OFF");
      break;

    case DESSERRAGE:
      digitalWrite(PIN_POMPE, RELAIS_OFF);
      digitalWrite(PIN_VANNE, RELAIS_ON);
      Serial.println("ETAT DESSERRAGE : pompe OFF, vanne ON");
      break;

    case STOP:
      digitalWrite(PIN_POMPE, RELAIS_OFF);
      digitalWrite(PIN_VANNE, RELAIS_OFF);
      Serial.println("ETAT STOP : pompe OFF, vanne OFF (maintien)");
      break;

    case REGONFLAGE:
      digitalWrite(PIN_POMPE, RELAIS_ON);
      digitalWrite(PIN_VANNE, RELAIS_OFF);
      Serial.println("ETAT REGONFLAGE : pompe ON, vanne OFF");
      break;

    case ARRET_URGENCE:
      digitalWrite(PIN_POMPE, RELAIS_OFF);
      digitalWrite(PIN_VANNE, RELAIS_ON);
      Serial.println("ETAT ARRET_URGENCE : pompe OFF, vanne ON (securite)");
      break;
  }
}

void changerEtat(EtatSysteme nouvelEtat) {
  etatSysteme = nouvelEtat;
  appliquerEtatSysteme();
}

// =========================
// Fonction : commande vocale reçue par Bluetooth
// =========================
void traiterCommandeBluetooth(String commande) {
  commande.trim();

  if (commande == "URGENCE") {
    changerEtat(ARRET_URGENCE);
    return;
  }

  // Aucune commande de mouvement n'est acceptee en arret d'urgence : seul le
  // bouton physique peut en sortir (reset volontaire, voir loop()).
  if (etatSysteme == ARRET_URGENCE) {
    if (commande.length() > 0 && commande != "PING") {
      Serial.println("Commande ignoree : ARRET_URGENCE actif, reset bouton requis");
    }
    return;
  }

  if (commande == "SERRER") {
    if (etatSysteme == INACTIF || etatSysteme == STOP) {
      changerEtat(SERRAGE);
    }
  } else if (commande == "DESSERRER") {
    if (etatSysteme == STOP || etatSysteme == SERRAGE) {
      changerEtat(DESSERRAGE);
    }
  } else if (commande == "STOP") {
    if (etatSysteme == SERRAGE || etatSysteme == DESSERRAGE || etatSysteme == REGONFLAGE) {
      changerEtat(STOP);
    }
  } else if (commande == "REGONFLER") {
    if (etatSysteme == STOP) {
      changerEtat(REGONFLAGE);
    }
  } else if (commande == "PING") {
    dernierPingRecu = millis();
    liaisonBTActive = true;
  } else if (commande.length() > 0) {
    Serial.print("Commande Bluetooth inconnue ignoree : ");
    Serial.println(commande);
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(PIN_POMPE, OUTPUT);
  pinMode(PIN_VANNE, OUTPUT);
  pinMode(PIN_BOUTON, INPUT_PULLUP);

  changerEtat(INACTIF);

  SerialBT.begin("ESP32-GANT-POMPE");
  Serial.println("Système prêt.");
  Serial.print("Adresse MAC Bluetooth : ");
  Serial.println(SerialBT.getBtAddressString());
}

void loop() {
  bool etatBouton = digitalRead(PIN_BOUTON);

  // Bouton physique : dedie a l'arret d'urgence.
  // - Depuis n'importe quel etat : force ARRET_URGENCE.
  // - Depuis ARRET_URGENCE : reset manuel vers INACTIF.
  if (ancienEtatBouton == HIGH && etatBouton == LOW) {
    if (etatSysteme == ARRET_URGENCE) {
      Serial.println("BOUTON : reset arret d'urgence -> INACTIF");
      changerEtat(INACTIF);
    } else {
      Serial.println("BOUTON : arret d'urgence declenche");
      changerEtat(ARRET_URGENCE);
    }
  }

  ancienEtatBouton = etatBouton;

  // Lecture des commandes vocales envoyees par le Raspberry Pi
  while (SerialBT.available()) {
    char c = SerialBT.read();
    if (c == '\n') {
      traiterCommandeBluetooth(bufferBT);
      bufferBT = "";
    } else if (c != '\r') {
      bufferBT += c;
    }
  }

  // Transitions automatiques par duree
  unsigned long tempsEcoule = millis() - tempsDebutEtat;

  if (etatSysteme == SERRAGE && tempsEcoule >= DUREE_GONFLAGE) {
    Serial.println("Gonflage complet -> STOP");
    changerEtat(STOP);
  } else if (etatSysteme == DESSERRAGE && tempsEcoule >= DUREE_DESSERRAGE) {
    Serial.println("Desserrage termine -> INACTIF");
    changerEtat(INACTIF);
  } else if (etatSysteme == REGONFLAGE && tempsEcoule >= DUREE_REGONFLAGE) {
    Serial.println("Regonflage termine -> STOP");
    changerEtat(STOP);
  }

  // Fail-safe : liaison Bluetooth perdue (plus de PING) -> on relache
  if (liaisonBTActive &&
      millis() - dernierPingRecu > PING_TIMEOUT_MS &&
      etatSysteme != INACTIF && etatSysteme != ARRET_URGENCE) {

    Serial.println("SECURITE : liaison Bluetooth perdue -> retour INACTIF");

    changerEtat(INACTIF);
    liaisonBTActive = false;
  }

  delay(100); // Anti-rebond simple
}
