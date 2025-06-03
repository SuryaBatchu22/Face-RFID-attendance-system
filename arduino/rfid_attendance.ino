//Paste in arduino IDE to run

#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN     10
#define RST_PIN    9
#define BUZZER     8
#define GREEN_LED  A0
#define RED_LED    A1

MFRC522 mfrc522(SS_PIN, RST_PIN);

void setup() {
  Serial.begin(9600);
  SPI.begin();
  mfrc522.PCD_Init();
  pinMode(BUZZER, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
}

void loop() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

  if (cmd == "READ") {
    // attempt to read a tag for up to 10s (no initial beep now)
    unsigned long start = millis();
    bool found = false;
    while (millis() - start < 10000UL) {
      if (mfrc522.PICC_IsNewCardPresent() &&
          mfrc522.PICC_ReadCardSerial()) {
        // **beep on successful scan**
        tone(BUZZER, 1000);
        delay(200);
        noTone(BUZZER);

        // send UID back
        String uid = "";
        for (byte i = 0; i < mfrc522.uid.size; i++) {
          uid += String(mfrc522.uid.uidByte[i], HEX);
        }
        Serial.println(uid);
        mfrc522.PICC_HaltA();
        found = true;
        break;
      }
      delay(50);
    }
    if (!found) {
      Serial.println("NOTAG");
    }
  }
  else if (cmd == "Green") {
    digitalWrite(GREEN_LED, HIGH);
    delay(500);
    digitalWrite(GREEN_LED, LOW);
  }
  else if (cmd == "Red") {
    digitalWrite(RED_LED, HIGH);
    delay(500);
    digitalWrite(RED_LED, LOW);
  }
}
