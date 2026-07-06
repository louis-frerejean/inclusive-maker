// Test simple ESP32 : fait clignoter une LED sur D5.
// Sert a valider le cablage avant de brancher la vraie pompe/gant.

const int LED_PIN = 5; // D5 sur la carte ESP32 DevKitC

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  Serial.println("LED ON");
  delay(1000);

  digitalWrite(LED_PIN, LOW);
  Serial.println("LED OFF");
  delay(1000);
}
