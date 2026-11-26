# GARUDA Commander Dashboard

A small, onboarding-friendly Django application for the GARUDA Base Station MQTT contract. The browser view shows received data only; a new soldier is **Unknown**, a stale connection is **Offline**, and unavailable GPS is **Unknown**. No sample or simulated hardware readings are created.

## What talks to what

```text
Soldier Node --LoRa--> ESP32 Base Station --MQTT QoS 0--> Django listener
                                                      |--> SQLite / PostgreSQL
Commander Dashboard --REST / WebSocket--------------|
         | commander confirms                         |
         +---- garuda/base/commands -----------------> Base Station
                     Base Station --LoRa confirmation--> Soldier
         Soldier --CONFIRM_RECEIVED--> Base --> MQTT confirmation --> dashboard
```

The dashboard confirmation means the command was accepted for MQTT publish. The request stays **PENDING** until the Base Station reports `CONFIRMED_DELIVERED`; after exhausted firmware retries it shows `DELIVERY_UNKNOWN` and remains incomplete.

## Windows PowerShell: first run

Open PowerShell in `C:\Users\diamo\Desktop\IOT_Project\Code_Base\WEB_Code_Base`:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`: set `MQTT_HOST` to the machine running your broker (for a local Mosquitto broker on this PC, use its LAN IP for the ESP32 too); set broker port and credentials. For PostgreSQL, set `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/garuda`.

```powershell
python manage.py migrate
python manage.py createsuperuser
```

Run the web app and MQTT listener in **two PowerShell windows**, activating the venv in each:

```powershell
python manage.py runserver
```

```powershell
python manage.py runmqtt
```

Visit `http://127.0.0.1:8000/` and sign in with the superuser. The admin console is at `/admin/`. To stop a process, press `Ctrl+C`.

If PowerShell blocks activation for the current terminal, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and activate again.

## Firmware contract implemented

Subscribed topics are exactly `garuda/soldiers/+/telemetry`, `/alert`, `/backup`, `/location`, `garuda/base/status`, and `garuda/base/confirmation`. Each event is deduplicated by `(topic, event_id)`, as provided by this firmware. Soldier topics require an alphanumeric `soldier_id` matching the topic. The documented telemetry fields (`heart_rate`, `ax/ay/az`, `touch`, `distress`, `reason`, `gps_valid`, coordinates, sensor/risk flags, status, `rssi`, `snr`, `sequence`, and `uptime`) are stored when present; optional/invalid GPS stays unknown.

Commander response publishes to `garuda/base/commands`:

```json
{"command":"COMMANDER_CONFIRMED","soldier_id":"S01","request_id":"REQ001","command_id":"CMD..."}
```

The listener tracks `SEEN_AWAITING_COMMANDER`, `PENDING`, `CONFIRMED_DELIVERED`, and `DELIVERY_UNKNOWN`. Firmware messages with `event_id` are application-deduplicated; MQTT transport remains QoS 0 per the firmware. `RESET_DISTRESS` is accepted by the base station contract but is intentionally not exposed as a dashboard button.

## API and live updates

- `GET /api/soldiers/`
- `GET /api/soldiers/{id}/`
- `GET /api/soldiers/timeline/`
- `GET /api/backup-requests/`
- `POST /api/backup-requests/{id}/confirm/` (authenticated)
- WebSocket `/ws/dashboard/` (authenticated; Channels in-memory layer for first run)

SQLite is the default. PostgreSQL uses the same models and migrations. Configure broker and database values only in `.env`; do not commit credentials. For multiple web workers, configure a shared Channels Redis layer before deployment.

## Tests

```powershell
python manage.py test dashboard
```

The tests cover contract parsing and GPS validation, deduplication, command topic and payload, and the pending/delivered/unknown backup states. Hardware, radio behavior, real broker access, and production deployment are not verified by these tests.

