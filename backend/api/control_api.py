"""Grafana control routes integrated into the existing Azure History Flask process.

This Flask service serves JSON APIs only; there is no second control dashboard.
Business Forms panels on http://localhost:3000 use a session cookie + CSRF token.
Never store credentials inside Grafana dashboard JSON or JavaScript.

Launched by: python backend/azure/history_api.py (the existing startup command)
Required private .env: CONTROL_USERNAME, CONTROL_PASSWORD (>=12 characters),
 CONTROL_SESSION_SECRET (>=32 characters), MQTT_PASSWORD.
Optional: CONTROL_ALLOWED_ORIGINS (comma-separated); MQTT_CONTROL_USERNAME,
 MQTT_CONTROL_PASSWORD, MQTT_HOST, MQTT_PORT.

Educational monitoring and threshold configuration only; this service does not
control machine power. Do not expose Flask to a public network.
"""
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
import hmac
import json
import logging
import math
import os
from pathlib import Path
import secrets
import threading
import time
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, request, session
import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
DEVICE = 'ESP32-001'
BASE = f'equipment/{DEVICE}'
CMD_TOPIC = BASE + '/commands'
ACK_TOPIC = BASE + '/command_ack'
CFG_TOPIC = BASE + '/config'
STATUS_TOPIC = BASE + '/control_status'
HEALTH_TOPIC = BASE + '/sensor_health'

CONTROL_USERNAME = os.getenv('CONTROL_USERNAME', 'operator')
CONTROL_PASSWORD = os.getenv('CONTROL_PASSWORD', '')
SESSION_SECRET = os.getenv('CONTROL_SESSION_SECRET', '')
MQTT_HOST = os.getenv('MQTT_HOST', '127.0.0.1')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USERNAME = os.getenv('MQTT_CONTROL_USERNAME') or os.getenv('MQTT_USERNAME', 'esp32_monitor')
MQTT_PASSWORD = os.getenv('MQTT_CONTROL_PASSWORD') or os.getenv('MQTT_PASSWORD', '')
ALLOWED_ORIGINS = {
    o.strip() for o in os.getenv(
        'CONTROL_ALLOWED_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000'
    ).split(',') if o.strip()
}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SESSION_SECRET or 'TEST_ONLY_DO_NOT_RUN_WITHOUT_SECRET',
    SESSION_COOKIE_NAME='iot_v2_operator',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Strict',
    SESSION_COOKIE_SECURE=False,  # Local HTTP only. Require True when behind HTTPS.
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    MAX_CONTENT_LENGTH=4096,
)
log = logging.getLogger('iot-control')
shared_lock = threading.RLock()
shared = {
    'config': None, 'control_status': None, 'sensor_health': None,
    'last_ack': None, 'connected': False, 'received_at': {}
}
pending = {}  # command ID -> {'event': Event, 'ack': dict | None}
audit = deque(maxlen=250)  # In-memory prototype audit; no credentials stored.
failed_logins = defaultdict(deque)  # Rate limit by loopback client IP.
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                     client_id='iot-v2-grafana-' + uuid4().hex[:8])
if MQTT_PASSWORD:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)


def on_connect(mqtt_client, _userdata, _flags, reason, _properties):
    connected = reason == 0
    with shared_lock:
        shared['connected'] = connected
    if connected:
        mqtt_client.subscribe([(ACK_TOPIC, 1), (CFG_TOPIC, 1),
                               (STATUS_TOPIC, 1), (HEALTH_TOPIC, 1)])
        log.info('Connected to MQTT broker')
    else:
        log.error('MQTT refused control connection: %s', reason)


def on_disconnect(_mqtt_client, _userdata, _flags, _reason, _properties):
    with shared_lock:
        shared['connected'] = False


def on_message(_mqtt_client, _userdata, message):
    try:
        body = json.loads(message.payload.decode('utf-8'))
        if not isinstance(body, dict) or body.get('device_id') != DEVICE:
            return
    except (ValueError, UnicodeError):
        return
    with shared_lock:
        names = {CFG_TOPIC: 'config', STATUS_TOPIC: 'control_status',
                 HEALTH_TOPIC: 'sensor_health', ACK_TOPIC: 'last_ack'}
        name = names.get(message.topic)
        if name:
            shared[name] = body
            shared['received_at'][name] = datetime.now(timezone.utc).isoformat()
        if message.topic == ACK_TOPIC:
            item = pending.get(str(body.get('command_id', '')))
            if item is not None:
                item['ack'] = body
                item['event'].set()


client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message


def snapshot():
    with shared_lock:
        return {**shared, 'received_at': dict(shared['received_at'])}


def _number(value, field):
    if value is None or isinstance(value, bool):
        raise ValueError(f'{field} must be a number')
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field} must be a number') from None
    if not math.isfinite(value):
        raise ValueError(f'{field} must be finite')
    return value


def make_threshold_command(body):
    metric = str(body.get('metric', '')).strip()
    if metric not in ('temperature', 'humidity', 'vibration'):
        raise ValueError('Unknown sensor metric')
    keys = ('warning_high', 'critical_high') if metric == 'vibration' else (
        'critical_low', 'warning_low', 'warning_high', 'critical_high')
    values = {key: _number(body.get(key), key) for key in keys}
    if metric == 'vibration':
        if not (0 <= values['warning_high'] < values['critical_high'] <= 200):
            raise ValueError('Vibration must have 0 <= warning < critical <= 200')
    else:
        a, b, c, d = (values[k] for k in keys)
        if not (a < b < c < d):
            raise ValueError('Must satisfy critical_low < warning_low < warning_high < critical_high')
        if metric == 'humidity' and not (0 <= a and d <= 100):
            raise ValueError('Humidity thresholds must remain within 0–100%')
        if metric == 'temperature' and not (-50 <= a and d <= 125):
            raise ValueError('Temperature thresholds must remain within -50–125°C')
    return {'action': 'SET_THRESHOLDS', 'metric': metric, **values}


def make_fan_temperatures(body):
    on = _number(body.get('on_temperature'), 'on_temperature')
    off = _number(body.get('off_temperature'), 'off_temperature')
    cfg = snapshot()['config'] or {}
    high = (cfg.get('temperature') or {}).get('critical_high', 70)
    if not (-40 <= off < on < float(high)):
        raise ValueError('Fan temperatures require -40 <= OFF < ON < temperature critical-high')
    return {'action': 'SET_FAN_TEMPERATURES', 'on_temperature': on,
            'off_temperature': off}


def issue_command(command, timeout=6):
    """Reports APPLIED only after matching ESP32 ack; no optimistic success."""
    if not _control_started or not client.is_connected() or not snapshot()['connected']:
        return {'status': 'ERROR', 'reason': 'CONTROL_BROKER_OFFLINE'}
    command_id = uuid4().hex
    payload = {**command, 'command_id': command_id,
               'device_id': DEVICE, 'expires_at': int(time.time()) + 12}
    item = {'event': threading.Event(), 'ack': None}
    with shared_lock:
        pending[command_id] = item
    try:
        result = client.publish(CMD_TOPIC, json.dumps(payload), qos=1, retain=False)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            return {'status': 'ERROR', 'reason': f'MQTT_PUBLISH_ERROR_{result.rc}'}
        if not item['event'].wait(timeout):
            return {'status': 'TIMEOUT', 'reason': 'ESP32 acknowledgement missing',
                    'command_id': command_id}
        ack = item['ack']
        if not ack or ack.get('command_id') != command_id:
            return {'status': 'ERROR', 'reason': 'INVALID_COMMAND_ACK'}
        return ack
    finally:
        with shared_lock:
            pending.pop(command_id, None)


def record_action(action, result):
    with shared_lock:
        audit.appendleft({
            'at': datetime.now(timezone.utc).isoformat(),
            'action': action, 'status': result.get('status', 'ERROR'),
            'reason': result.get('reason', ''),
            'command_id': result.get('command_id')
        })
    return result


def response_for(result):
    status = result.get('status', 'ERROR')
    http = 200 if status == 'APPLIED' else (504 if status == 'TIMEOUT' else 409)
    return jsonify(result), http


def logged_in():
    return session.get('operator') is True


def require_operator(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not logged_in():
            return jsonify({'error': 'operator_login_required'}), 401
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            candidate = request.headers.get('X-CSRF-Token', '')
            expected = session.get('csrf', '')
            if not expected or not hmac.compare_digest(candidate, expected):
                return jsonify({'error': 'csrf_token_invalid'}), 403
        return fn(*args, **kwargs)
    return wrapped


@app.before_request
def enforce_local_security():
    if request.path.startswith('/api/'):
        origin = request.headers.get('Origin')
        if origin and origin not in ALLOWED_ORIGINS:
            return jsonify({'error': 'origin_not_allowed'}), 403
        if request.method == 'OPTIONS':
            return make_response('', 204)
        if request.method in ('POST', 'PUT', 'PATCH') and not request.is_json:
            return jsonify({'error': 'application_json_required'}), 415


@app.after_request
def cors_and_no_cache(response):
    origin = request.headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRF-Token'
        response.headers['Vary'] = 'Origin'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.get('/api/health')
def health():
    # Preserve the historical API health contract, adding control connectivity.
    return jsonify({'status': 'OK',
                    'service': 'IoT Historical Data API',
                    'control_enabled': _control_started,
                    'mqtt_connected': snapshot()['connected']})


@app.get('/api/session')
def session_status():
    if not logged_in():
        return jsonify({'authenticated': False, 'csrf': None}), 401
    return jsonify({'authenticated': True, 'username': CONTROL_USERNAME,
                    'csrf': session['csrf']})


@app.post('/api/session')
def session_login():
    # Independent authorization; Grafana login alone grants NO motor permissions.
    now = time.monotonic()
    ip = request.remote_addr or '127.0.0.1'
    attempts = failed_logins[ip]
    while attempts and now - attempts[0] > 120:
        attempts.popleft()
    if len(attempts) >= 6:
        return jsonify({'error': 'too_many_attempts_retry_later'}), 429
    body = request.get_json(silent=True) or {}
    supplied_user = str(body.get('username', ''))
    supplied_password = str(body.get('password', ''))
    good_user = hmac.compare_digest(supplied_user, CONTROL_USERNAME)
    good_password = hmac.compare_digest(supplied_password, CONTROL_PASSWORD)
    if not (good_user and good_password and len(CONTROL_PASSWORD) >= 12):
        attempts.append(now)
        return jsonify({'error': 'invalid_operator_credentials'}), 401
    attempts.clear()
    session.clear()
    session.permanent = True
    session['operator'] = True
    session['csrf'] = secrets.token_urlsafe(32)
    return jsonify({'authenticated': True, 'csrf': session['csrf']})


@app.delete('/api/session')
@require_operator
def session_logout():
    session.clear()
    return jsonify({'authenticated': False})


@app.get('/api/config')
@require_operator
def get_config():
    cfg = snapshot()['config']
    if cfg is None:
        return jsonify({'error': 'No confirmed ESP32 configuration available'}), 503
    return jsonify(cfg)


@app.get('/api/control/status')
@require_operator
def control_status():
    return jsonify(snapshot())


@app.get('/api/audit')
@require_operator
def control_audit():
    with shared_lock:
        return jsonify(list(audit))


@app.post('/api/config')
@require_operator
def set_thresholds():
    try:
        command = make_threshold_command(request.get_json(silent=True) or {})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return response_for(record_action(command['action'] + ':' + command['metric'],
                                      issue_command(command)))


@app.post('/api/profile')
@require_operator
def select_profile():
    """Switch demonstration equipment profile (no physical motor)."""
    profile = (request.get_json(silent=True) or {}).get('profile')
    if profile not in ('MOTOR', 'PUMP', 'COMPRESSOR', 'FAN', 'CONDENSER', 'HEAT_EXCHANGER', 'AHU', 'CHILLER'):
        return jsonify({'error': 'invalid_profile'}), 400
    command = {'action': 'SET_PROFILE', 'profile': profile}
    return response_for(record_action('SET_PROFILE:' + profile, issue_command(command)))


@app.post('/api/alarm/ack')
@require_operator
def acknowledge_alarm():
    """Acknowledge audible alert; does not clear active WARNING/CRITICAL."""
    return response_for(record_action('ACK_ALARM', issue_command({'action': 'ACK_ALARM'})))


@app.post('/api/config/refresh')
@require_operator
def refresh_config():
    return response_for(record_action('GET_CONFIG',
                                      issue_command({'action': 'GET_CONFIG'})))


# MQTT client starts in the existing History API process. There is no second Flask
# listener, no additional TCP listener, and no additional startup command.
_control_started = False

def start_control_mqtt():
    """Enable controls without preventing the existing History API from starting.

    Missing secrets -> controls fail closed; historical charts still work.
    """
    global _control_started
    if _control_started:
        return True
    if len(CONTROL_PASSWORD) < 12 or len(SESSION_SECRET) < 32 or not MQTT_PASSWORD:
        log.warning('Control endpoints DISABLED: set private CONTROL_PASSWORD (12+), '
                    'CONTROL_SESSION_SECRET (32+), and MQTT_PASSWORD in .env. '
                    'Azure historical endpoints remain available.')
        return False
    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()
        _control_started = True
        log.info('Integrated control MQTT listener started inside History API process')
        return True
    except (OSError, ValueError, RuntimeError) as exc:
        # Don't break historical monitoring when the control MQTT connection fails.
        log.error('Control MQTT listener failed: %s', type(exc).__name__)
        return False


def stop_control_mqtt():
    global _control_started
    if _control_started:
        client.disconnect()
        client.loop_stop()
        _control_started = False


if __name__ == '__main__':
    raise SystemExit('Do not run control_api.py separately. '
                     'Start the existing backend/azure/history_api.py instead.')
