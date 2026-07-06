// Sketch de TEST pour valider le protocole Bluetooth Pi <-> ESP32 (Fork 1).
// Ce n'est PAS le firmware final de la pompe/du gant (fait par Cecile) : ici,
// deux LEDs simulent juste l'etat "ouvert"/"ferme" pour verifier que les
// commandes OUVRIR / FERMER / PING envoyees par gant_link.py arrivent bien.
//
// Branchement (memes broches que celles prevues par Cecile pour la pompe) :
//   D5  -> resistance -> LED "OUVRIR" -> GND
//   D18 -> resistance -> LED "FERMER" -> GND

#include "BluetoothSerial.h"

BluetoothSerial SerialBT;

const int LED_OUVRIR = 5;   // D5
const int LED_FERMER = 18;  // D18

const unsigned long PING_TIMEOUT_MS = 3000; // fail-safe si plus de PING recu
unsigned long lastPingTime = 0;
bool linkWasAlive = false;

String buffer = "";

void handleCommand(String cmd) {
  cmd.trim();
  if (cmd == "OUVRIR") {
    digitalWrite(LED_OUVRIR, HIGH);
    digitalWrite(LED_FERMER, LOW);
    Serial.println("Commande recue : OUVRIR");
  } else if (cmd == "FERMER") {
    digitalWrite(LED_OUVRIR, LOW);
    digitalWrite(LED_FERMER, HIGH);
    Serial.println("Commande recue : FERMER");
  } else if (cmd == "PING") {
    lastPingTime = millis();
    linkWasAlive = true;
  } else if (cmd.length() > 0) {
    Serial.print("Commande inconnue ignoree : ");
    Serial.println(cmd);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_OUVRIR, OUTPUT);
  pinMode(LED_FERMER, OUTPUT);
  digitalWrite(LED_OUVRIR, LOW);
  digitalWrite(LED_FERMER, LOW);

  SerialBT.begin("ESP32-GANT-TEST");
  Serial.println("Bluetooth pret, en attente d'appairage.");
  Serial.print("Adresse MAC de la carte : ");
  Serial.println(SerialBT.getBtAddressString());
}

void loop() {
  while (SerialBT.available()) {
    char c = SerialBT.read();
    if (c == '\n') {
      handleCommand(buffer);
      buffer = "";
    } else if (c != '\r') {
      buffer += c;
    }
  }

  // Fail-safe : si plus de PING depuis PING_TIMEOUT_MS alors que la liaison
  // etait active, on considere la liaison perdue et on coupe tout.
  if (linkWasAlive && millis() - lastPingTime > PING_TIMEOUT_MS) {
    digitalWrite(LED_OUVRIR, LOW);
    digitalWrite(LED_FERMER, LOW);
    Serial.println("Liaison perdue (pas de PING) -> fail-safe, LEDs eteintes");
    linkWasAlive = false;
  }
}
