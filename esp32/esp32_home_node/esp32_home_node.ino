/*
 * ESP32 智能家居桌面原型节点
 * - 传感器：DHT22 / BH1750 / HC-SR501
 * - 执行器：LED（灯）+ 5V 风扇（MOSFET/继电器）
 * - 通信：MQTT home/v1/{room}/{device}/...
 *
 * 仅低压演示，禁止接入 220V 市电。
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <Wire.h>
#include <BH1750.h>
#include <ArduinoJson.h>

// ====== 用户配置 ======
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_HOST = "192.168.1.100";
const uint16_t MQTT_PORT = 1883;
const char* MQTT_USER = "";   // 可选
const char* MQTT_PASSWORD = "";

const char* ROOM = "study";
const char* LIGHT_DEVICE_ID = "desk_light";
const char* FAN_DEVICE_ID = "desk_fan";

// 引脚（按实际接线修改）
const int PIN_LED = 25;      // 灯 LED
const int PIN_FAN = 26;      // 风扇控制（MOSFET/继电器）
const int PIN_DHT = 4;       // DHT22
const int PIN_PIR = 27;      // HC-SR501
const int PIN_SDA = 21;
const int PIN_SCL = 22;

const uint32_t TELEMETRY_MS = 5000;
const uint32_t COMMAND_TTL_MS = 15000;

DHT dht(PIN_DHT, DHT22);
BH1750 lightMeter;
WiFiClient espClient;
PubSubClient mqttClient(espClient);

bool ledOn = false;
bool fanOn = false;
uint32_t lastTelemetry = 0;
String lastLightRequestId = "";
String lastFanRequestId = "";

String topicSet(const char* deviceId) {
  return String("home/v1/") + ROOM + "/" + deviceId + "/state/set";
}
String topicAck(const char* deviceId) {
  return String("home/v1/") + ROOM + "/" + deviceId + "/state/ack";
}
String topicTelemetry(const char* deviceId) {
  return String("home/v1/") + ROOM + "/" + deviceId + "/telemetry";
}
String topicAvailability(const char* deviceId) {
  return String("home/v1/") + ROOM + "/" + deviceId + "/availability";
}
String topicNodeAvailability() {
  return String("home/v1/") + ROOM + "/availability";
}

void applyOutputs() {
  digitalWrite(PIN_LED, ledOn ? HIGH : LOW);
  digitalWrite(PIN_FAN, fanOn ? HIGH : LOW);
}

void publishAck(const char* deviceId, const String& requestId, bool accepted, const char* state, const char* message) {
  String payload = "{\"request_id\":\"" + requestId + "\",\"accepted\":";
  payload += accepted ? "true" : "false";
  payload += ",\"state\":\"";
  payload += state;
  payload += "\",\"message\":\"";
  payload += message;
  payload += "\",\"device_id\":\"";
  payload += deviceId;
  payload += "\"}";
  mqttClient.publish(topicAck(deviceId).c_str(), payload.c_str(), false);
}

void publishAvailability(bool online) {
  String payload = online ? "{\"online\":true}" : "{\"online\":false}";
  mqttClient.publish(topicNodeAvailability().c_str(), payload.c_str(), true);
  mqttClient.publish(topicAvailability(LIGHT_DEVICE_ID).c_str(), payload.c_str(), true);
  mqttClient.publish(topicAvailability(FAN_DEVICE_ID).c_str(), payload.c_str(), true);
}

void publishTelemetryFor(const char* deviceId, bool stateOn) {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  float lux = lightMeter.readLightLevel();
  int motion = digitalRead(PIN_PIR) == HIGH ? 1 : 0;

  if (isnan(t) || isnan(h)) {
    t = 0;
    h = 0;
  }

  String payload = "{\"state\":\"";
  payload += stateOn ? "on" : "off";
  payload += "\",\"sensors\":{";
  payload += "\"room_temp\":";
  payload += String(t, 1);
  payload += ",\"room_humidity\":";
  payload += String(h, 1);
  payload += ",\"room_light\":";
  payload += String(lux, 1);
  payload += ",\"room_motion\":";
  payload += motion;
  payload += "}}";
  mqttClient.publish(topicTelemetry(deviceId).c_str(), payload.c_str(), false);
}

void publishTelemetry() {
  publishTelemetryFor(LIGHT_DEVICE_ID, ledOn);
  publishTelemetryFor(FAN_DEVICE_ID, fanOn);
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  const char* deviceId = nullptr;
  bool* targetState = nullptr;
  String* lastRequestId = nullptr;
  if (String(topic) == topicSet(LIGHT_DEVICE_ID)) {
    deviceId = LIGHT_DEVICE_ID;
    targetState = &ledOn;
    lastRequestId = &lastLightRequestId;
  } else if (String(topic) == topicSet(FAN_DEVICE_ID)) {
    deviceId = FAN_DEVICE_ID;
    targetState = &fanOn;
    lastRequestId = &lastFanRequestId;
  } else {
    return;
  }

  String msg;
  for (unsigned int i = 0; i < length; i++) {
    msg += (char)payload[i];
  }

  StaticJsonDocument<256> command;
  DeserializationError parseError = deserializeJson(command, msg);
  if (parseError) {
    publishAck(deviceId, "unknown", false, *targetState ? "on" : "off", "invalid json");
    return;
  }
  String requestId = command["request_id"] | "unknown";
  String action = command["action"] | "";
  String state = command["state"] | "";

  if (*lastRequestId == requestId && requestId != "unknown") {
    // 幂等：重复 request_id 不再执行，只回成功
    publishAck(deviceId, requestId, true, *targetState ? "on" : "off", "duplicate request ignored");
    return;
  }

  if (action != "set_state") {
    publishAck(deviceId, requestId, false, *targetState ? "on" : "off", "unsupported action");
    return;
  }
  if (state == "on") {
    *targetState = true;
  } else if (state == "off") {
    *targetState = false;
  } else {
    publishAck(deviceId, requestId, false, *targetState ? "on" : "off", "unsupported state");
    return;
  }

  applyOutputs();
  *lastRequestId = requestId;
  publishAck(deviceId, requestId, true, *targetState ? "on" : "off", "acknowledged by esp32");
  publishTelemetry();
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("WiFi connected: ");
  Serial.println(WiFi.localIP());
}

void connectMqtt() {
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setCallback(onMqttMessage);
  while (!mqttClient.connected()) {
    String clientId = String("esp32-") + ROOM;
    bool ok = false;
    if (strlen(MQTT_USER) > 0) {
      ok = mqttClient.connect(
        clientId.c_str(), MQTT_USER, MQTT_PASSWORD,
        topicNodeAvailability().c_str(), 1, true, "{\"online\":false}"
      );
    } else {
      ok = mqttClient.connect(
        clientId.c_str(), topicNodeAvailability().c_str(), 1, true, "{\"online\":false}"
      );
    }
    if (ok) {
      mqttClient.subscribe(topicSet(LIGHT_DEVICE_ID).c_str());
      mqttClient.subscribe(topicSet(FAN_DEVICE_ID).c_str());
      publishAvailability(true);
      publishTelemetry();
      Serial.println("MQTT connected");
    } else {
      Serial.print("MQTT failed, rc=");
      Serial.println(mqttClient.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_FAN, OUTPUT);
  pinMode(PIN_PIR, INPUT);
  applyOutputs();

  Wire.begin(PIN_SDA, PIN_SCL);
  dht.begin();
  lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE);

  connectWifi();
  connectMqtt();
}

void loop() {
  if (!mqttClient.connected()) {
    connectMqtt();
  }
  mqttClient.loop();

  uint32_t now = millis();
  if (now - lastTelemetry >= TELEMETRY_MS) {
    lastTelemetry = now;
    publishTelemetry();
  }
}
