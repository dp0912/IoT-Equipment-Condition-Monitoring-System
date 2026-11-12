#pragma once

// Public example only. Do not place real passwords here.

// Password for the EquipmentMonitor-Setup Wi-Fi portal.
// Choose a private password of at least 8 characters.
#define WIFI_SETUP_AP_PASSWORD "REPLACE_WITH_PRIVATE_SETUP_PASSWORD"

// Azure secure MQTT broker.
#define MQTT_SERVER "iot-monitor-dp0912.northcentralus.cloudapp.azure.com"
#define MQTT_PORT 8883

#define MQTT_USERNAME "esp32_monitor"
#define MQTT_PASSWORD "REPLACE_WITH_PRIVATE_MQTT_PASSWORD"

// Copy this file to secrets.h and enter private credentials.
// The real secrets.h file is excluded from Git.
