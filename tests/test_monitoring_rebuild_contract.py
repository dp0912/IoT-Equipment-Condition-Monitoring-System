"""Offline structural checks for the current monitoring-only prototype."""
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class MonitoringContract(unittest.TestCase):
    def test_firmware_monitoring_only(self):
        s = (ROOT/'firmware/esp32/equipment_monitor/equipment_monitor.ino').read_text()
        for required in ('PIN_DHT = 27', 'PIN_BUZZER = 23', 'BUZZER_ENABLED = true', 'SET_PROFILE', 'SET_THRESHOLDS', 'ACK_ALARM', 'dht_valid', 'vibration_valid', 'sensor_fault', 'TOPIC_CONFIG', 'TOPIC_ACK'):
            self.assertIn(required, s)
        for removed in ('configVersion', 'motor_running', 'motor_armed', 'stop_latched', 'sensor_condition', 'L293D.h'):
            self.assertNotIn(removed, s)

    def test_dashboard_integrity(self):
        d = json.loads((ROOT/'dashboard/grafana/iot-equipment-live-dashboard.json').read_text())
        els = d['spec']['elements']
        self.assertEqual(len(els), 22)
        refs = {i['spec']['element']['name'] for i in d['spec']['layout']['spec']['items']}
        self.assertEqual(refs, set(els))
        for n in range(1, 23): self.assertIn(f'panel-{n}', els)
        self.assertIn('control_status', str(els['panel-17']['spec']))
        self.assertIn('/api/config', str(els['panel-19']['spec']))
        self.assertIn('/api/profile', str(els['panel-22']['spec']))

    def test_profile_alerts(self):
        subscriber=(ROOT/'backend/mqtt/subscriber.py').read_text()
        self.assertEqual(subscriber.count('equipment_type=data.get("profile", "UNKNOWN")'), 2)
        notifier=(ROOT/'backend/notifications/email_notifier.py').read_text()
        self.assertIn('equipment_type=None', notifier)
        self.assertIn('Equipment: {equipment}', notifier)

if __name__ == '__main__': unittest.main()
