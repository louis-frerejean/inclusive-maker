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
      "REGONFLER" -> depuis n'importe quel etat (sauf ARRET_URGENCE), recharge
                     courte (DUREE_REGONFLAGE) pour remettre un peu d'air sans
                     repasser par un cycle de gonflage complet, puis revient
                     seule en STOP
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

    Moniteur série : chaque ligne est préfixée par catégorie pour pouvoir
    filtrer facilement ([ETAT], [BT], [CMD], [BOUTON], [STATUT]). Une ligne
    [STATUT] périodique résume l'état courant (utile en démo/débogage).
  ============================================================
*/

#include "BluetoothSerial.h"

BluetoothSerial SerialBT;
String bufferBT = "";

const unsigned long PING_TIMEOUT_MS = 3000;
unsigned long dernierPingRecu = 0;
bool liaisonBTActive = false;
bool clientBTConnecte = false;

const unsigned long STATUT_INTERVAL_MS = 2000;
unsigned long dernierStatutAffiche = 0;

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
const unsigned long DUREE_DESSERRAGE  = 5000; // 5 secondes
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
// Fonction : nom lisible d'un etat (pour les logs)
// =========================
const char* nomEtat(EtatSysteme e) {
  switch (e) {
    case INACTIF:       return "INACTIF";
    case SERRAGE:        return "SERRAGE";
    case DESSERRAGE:      return "DESSERRAGE";
    case STOP:            return "STOP";
    case REGONFLAGE:      return "REGONFLAGE";
    case ARRET_URGENCE:   return "ARRET_URGENCE";
  }
  return "?";
}

// Duree restante avant une transition automatique (0 si aucune prevue).
unsigned long dureeAutoTransition(EtatSysteme e) {
  switch (e) {
    case SERRAGE:    return DUREE_GONFLAGE;
    case DESSERRAGE: return DUREE_DESSERRAGE;
    case REGONFLAGE: return DUREE_REGONFLAGE;
    default:          return 0;
  }
}

// =========================
// Fonction : applique les sorties physiques de l'état
// =========================
void appliquerEtatSysteme() {
  switch (etatSysteme) {
    case INACTIF:
    case DESSERRAGE:
    case ARRET_URGENCE:
      digitalWrite(PIN_POMPE, RELAIS_OFF);
      digitalWrite(PIN_VANNE, RELAIS_ON);
      break;

    case SERRAGE:
    case REGONFLAGE:
      digitalWrite(PIN_POMPE, RELAIS_ON);
      digitalWrite(PIN_VANNE, RELAIS_OFF);
      break;

    case STOP:
      digitalWrite(PIN_POMPE, RELAIS_OFF);
      digitalWrite(PIN_VANNE, RELAIS_OFF);
      break;
  }
}

void changerEtat(EtatSysteme nouvelEtat, const char* raison) {
  EtatSysteme ancien = etatSysteme;
  etatSysteme = nouvelEtat;
  tempsDebutEtat = millis();
  appliquerEtatSysteme();

  Serial.print("[ETAT] ");
  Serial.print(nomEtat(ancien));
  Serial.print(" -> ");
  Serial.print(nomEtat(nouvelEtat));
  Serial.print("  (");
  Serial.print(raison);
  Serial.print(")  pompe=");
  Serial.print(digitalRead(PIN_POMPE) == RELAIS_ON ? "ON" : "OFF");
  Serial.print(" vanne=");
  Serial.println(digitalRead(PIN_VANNE) == RELAIS_ON ? "ON" : "OFF");
}

// =========================
// Fonction : commande vocale reçue par Bluetooth
// =========================
void traiterCommandeBluetooth(String commande) {
  commande.trim();
  if (commande.length() == 0) return;

  if (commande == "PING") {
    dernierPingRecu = millis();
    liaisonBTActive = true;
    return; // pas de log: recu en continu, inutile de polluer le moniteur
  }

  Serial.print("[CMD] Recue : ");
  Serial.println(commande);

  if (commande == "URGENCE") {
    changerEtat(ARRET_URGENCE, "commande vocale URGENCE");
    return;
  }

  // Aucune commande de mouvement n'est acceptee en arret d'urgence : seul le
  // bouton physique peut en sortir (reset volontaire, voir loop()).
  if (etatSysteme == ARRET_URGENCE) {
    Serial.println("[CMD] Ignoree : ARRET_URGENCE actif, reset par bouton requis");
    return;
  }

  if (commande == "SERRER") {
    if (etatSysteme == INACTIF || etatSysteme == STOP) {
      changerEtat(SERRAGE, "commande vocale SERRER");
    } else {
      Serial.print("[CMD] Ignoree : SERRER invalide depuis ");
      Serial.println(nomEtat(etatSysteme));
    }
  } else if (commande == "DESSERRER") {
    if (etatSysteme == STOP || etatSysteme == SERRAGE) {
      changerEtat(DESSERRAGE, "commande vocale DESSERRER");
    } else {
      Serial.print("[CMD] Ignoree : DESSERRER invalide depuis ");
      Serial.println(nomEtat(etatSysteme));
    }
  } else if (commande == "STOP") {
    if (etatSysteme == SERRAGE || etatSysteme == DESSERRAGE || etatSysteme == REGONFLAGE) {
      changerEtat(STOP, "commande vocale STOP");
    } else {
      Serial.print("[CMD] Ignoree : STOP invalide depuis ");
      Serial.println(nomEtat(etatSysteme));
    }
  } else if (commande == "REGONFLER") {
    // Pas de condition d'etat : sert a remettre un peu d'air quand la
    // pression a baisse, quel que soit le moment (pas seulement depuis STOP).
    changerEtat(REGONFLAGE, "commande vocale REGONFLER");
  } else {
    Serial.print("[CMD] Inconnue, ignoree : ");
    Serial.println(commande);
  }
}

void afficherStatut() {
  unsigned long tempsEcoule = millis() - tempsDebutEtat;
  unsigned long dureeAuto = dureeAutoTransition(etatSysteme);

  Serial.print("[STATUT] etat=");
  Serial.print(nomEtat(etatSysteme));
  Serial.print(" depuis=");
  Serial.print(tempsEcoule / 1000.0, 1);
  Serial.print("s");

  if (dureeAuto > 0) {
    long restant = (long)dureeAuto - (long)tempsEcoule;
    Serial.print(" auto_dans=");
    Serial.print(max(restant, 0L) / 1000.0, 1);
    Serial.print("s");
  }

  Serial.print(" pompe=");
  Serial.print(digitalRead(PIN_POMPE) == RELAIS_ON ? "ON" : "OFF");
  Serial.print(" vanne=");
  Serial.print(digitalRead(PIN_VANNE) == RELAIS_ON ? "ON" : "OFF");

  Serial.print(" bt_client=");
  Serial.print(clientBTConnecte ? "oui" : "non");

  Serial.print(" liaison_active=");
  if (liaisonBTActive) {
    Serial.print("oui (dernier ping il y a ");
    Serial.print((millis() - dernierPingRecu) / 1000.0, 1);
    Serial.print("s)");
  } else {
    Serial.print("non");
  }

  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(200);

  Serial.println();
  Serial.println("============================================");
  Serial.println(" Pomp_control_v3 - commande pompe/electrovanne");
  Serial.println("============================================");
  Serial.print("Broches  : POMPE=D"); Serial.print(PIN_POMPE);
  Serial.print(" VANNE=D"); Serial.print(PIN_VANNE);
  Serial.print(" BOUTON=D"); Serial.println(PIN_BOUTON);
  Serial.print("Durees   : gonflage="); Serial.print(DUREE_GONFLAGE / 1000);
  Serial.print("s desserrage="); Serial.print(DUREE_DESSERRAGE / 1000);
  Serial.print("s regonflage="); Serial.print(DUREE_REGONFLAGE / 1000);
  Serial.println("s");

  pinMode(PIN_POMPE, OUTPUT);
  pinMode(PIN_VANNE, OUTPUT);
  pinMode(PIN_BOUTON, INPUT_PULLUP);

  changerEtat(INACTIF, "demarrage");

  SerialBT.begin("ESP32-GANT-POMPE");
  Serial.print("Bluetooth: pret, nom \"ESP32-GANT-POMPE\", MAC ");
  Serial.println(SerialBT.getBtAddressString());
  Serial.println("============================================");
  Serial.println();
}

void loop() {
  bool etatBouton = digitalRead(PIN_BOUTON);

  // Bouton physique : dedie a l'arret d'urgence.
  // - Depuis n'importe quel etat : force ARRET_URGENCE.
  // - Depuis ARRET_URGENCE : reset manuel vers INACTIF.
  if (ancienEtatBouton == HIGH && etatBouton == LOW) {
    Serial.println("[BOUTON] Appui detecte");
    if (etatSysteme == ARRET_URGENCE) {
      changerEtat(INACTIF, "reset bouton apres urgence");
    } else {
      changerEtat(ARRET_URGENCE, "bouton physique");
    }
  }
  ancienEtatBouton = etatBouton;

  // Detection connexion/deconnexion d'un client Bluetooth (le Pi)
  bool clientMaintenant = SerialBT.hasClient();
  if (clientMaintenant != clientBTConnecte) {
    clientBTConnecte = clientMaintenant;
    Serial.print("[BT] Client ");
    Serial.println(clientBTConnecte ? "connecte" : "deconnecte");
  }

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
    changerEtat(STOP, "gonflage complet");
  } else if (etatSysteme == DESSERRAGE && tempsEcoule >= DUREE_DESSERRAGE) {
    changerEtat(INACTIF, "desserrage termine");
  } else if (etatSysteme == REGONFLAGE && tempsEcoule >= DUREE_REGONFLAGE) {
    changerEtat(STOP, "regonflage termine");
  }

  // Fail-safe : liaison Bluetooth perdue (plus de PING) -> on relache
  if (liaisonBTActive &&
      millis() - dernierPingRecu > PING_TIMEOUT_MS &&
      etatSysteme != INACTIF && etatSysteme != ARRET_URGENCE) {

    liaisonBTActive = false;
    changerEtat(INACTIF, "liaison Bluetooth perdue (fail-safe)");
  }

  // Ligne de statut periodique (debogage/demo) : seulement pendant les etats
  // avec un compte a rebours actif, pour ne pas polluer le moniteur quand
  // rien ne se passe (INACTIF/STOP/ARRET_URGENCE restent silencieux entre
  // deux transitions).
  if (dureeAutoTransition(etatSysteme) > 0 &&
      millis() - dernierStatutAffiche >= STATUT_INTERVAL_MS) {
    dernierStatutAffiche = millis();
    afficherStatut();
  }

  delay(100); // Anti-rebond simple
}
