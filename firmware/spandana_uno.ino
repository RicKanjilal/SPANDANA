/*
 * SPANDANA — Plant Stress Signal Detector
 * Firmware for Arduino Uno
 *
 * Reads a piezo disc taped to a plant stem alongside soil moisture,
 * temperature, humidity, and ambient light sensors. Streams a comma-
 * separated frame over USB serial every 50 ms in the format:
 *
 *   P,raw,delta,moisture,temp,humidity,ldr
 *
 * The host-side Python listener (host/spandana_listener.py) handles
 * adaptive baseline tracking, event detection, and classification.
 *
 * Wiring:
 *   Piezo (+)         → A0   (1MΩ pulldown to GND recommended)
 *   Soil moisture     → A1
 *   LDR               → A2   (10kΩ pulldown)
 *   DHT11 data        → D2
 *
 * Author : Ric Kanjilal, Grade 10, Don Bosco School, Liluah
 * Project: SPANDANA — YIP 2025–26 (Top 30 of 3,300+, IIT Kharagpur)
 * License: MIT
 */

#include <DHT.h>

#define PIEZO_PIN     A0
#define MOISTURE_PIN  A1
#define LDR_PIN       A2
#define DHTPIN        2
#define DHTTYPE       DHT11

DHT dht(DHTPIN, DHTTYPE);

int baseline = 0;

void setup() {
  Serial.begin(115200);
  dht.begin();

  // Baseline calibration — average 100 samples at boot to establish
  // the piezo's resting voltage. This is intentionally simple; the
  // real adaptive baseline lives on the host side.
  long sum = 0;
  for (int i = 0; i < 100; i++) {
    sum += analogRead(PIEZO_PIN);
    delay(5);
  }
  baseline = sum / 100;
}

void loop() {
  int   raw      = analogRead(PIEZO_PIN);
  int   delta    = abs(raw - baseline);
  int   moisture = analogRead(MOISTURE_PIN);
  int   ldr      = analogRead(LDR_PIN);
  float temp     = dht.readTemperature();
  float hum      = dht.readHumidity();

  Serial.print("P,");
  Serial.print(raw);      Serial.print(",");
  Serial.print(delta);    Serial.print(",");
  Serial.print(moisture); Serial.print(",");
  Serial.print(temp);     Serial.print(",");
  Serial.print(hum);      Serial.print(",");
  Serial.println(ldr);

  delay(50);
}
