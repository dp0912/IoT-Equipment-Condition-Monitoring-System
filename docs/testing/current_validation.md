# Current Prototype Validation Checklist

**Project:** IoT Equipment Condition Monitoring System
**Updated:** November 10, 2026
**Status:** Core pipeline demonstrated; comprehensive testing in progress.

**Evidence standard:** OBSERVED PASS means a result was confirmed from previous terminal output or dashboard testing. It does not mean that the service is currently running or that full acceptance testing is complete.

| ID | Test | Status | Evidence / Next Action |
|---|---|---|---|
| T01 | Final ESP32 firmware compilation/upload | NOT REVALIDATED | Original 1,259-line sketch restored; verify final physical upload |
| T02 | DHT11 and MPU sensor telemetry | OBSERVED PASS | Subscriber logs showed temperature, humidity and vibration |
| T03 | Four Docker services and authenticated MQTT | OBSERVED PASS | Mosquitto, subscriber, API and Grafana were Up |
| T04 | Flask API health | OBSERVED PASS | /api/health returned status OK and mqtt_connected true |
| T05 | 30-second aggregation | OBSERVED PASS | SUMMARY record generated from 13 measurements |
| T06 | Isolation Forest inference | OBSERVED PASS | Model loaded and ANOMALY result logged |
| T07 | Azure SUMMARY storage | OBSERVED PASS | Azure Table Storage write confirmed |
| T08 | Grafana dashboard | OBSERVED PASS | Dashboard functionality confirmed during integration |
| T09 | Azure EVENT records and retrieval | NEEDS TEST | Trigger event and verify database/history query |
| T10 | NORMAL, WARNING and CRITICAL LEDs | NEEDS TEST | Verify all three local outputs |
| T11 | Buzzer and physical acknowledgement | NEEDS TEST | Confirm 200/800 ms pattern and GPIO13 behaviour |
| T12 | All eight equipment profiles | NEEDS TEST | Apply and confirm each profile |
| T13 | Threshold changes and authorization | NEEDS TEST | Verify applied, rejected and unauthorized requests |
| T14 | Email delivery | NEEDS TEST | Test WARNING, CRITICAL, RECOVERY and connectivity emails |
| T15 | Offline and reconnect behaviour | NEEDS TEST | Disconnect/reconnect ESP32 |
| T16 | Persistent settings after restart | NEEDS TEST | Verify ESP32 Preferences and Docker persistence |
| T17 | Python unit tests and dashboard JSON | NEEDS TEST | Execute latest automated checks |
| T18 | SMS notifications | PLANNED | Not currently implemented |

## Final Test Evidence

For every test executed, record:

1. Test identifier.
2. Date and time.
3. Steps and configuration.
4. Expected result.
5. Actual result.
6. PASS or FAIL.
7. Supporting screenshot or sanitized log.

Do not mark a test passed merely because the supporting code exists.

## Automated Verification Commands

```bash
python3 -m compileall -q backend ml
python3 -m unittest discover -s tests -v
python3 -m json.tool dashboard/grafana/iot-equipment-live-dashboard.json > /dev/null
docker compose config --quiet
```

## Current Notes

The Docker stack was previously stopped intentionally after successful integration observations.

No production reliability or long-duration performance claims are made.

SMS/text notifications remain a planned enhancement.
