import json
import logging
import re
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import paho.mqtt.client as mqtt
from .models import BackupRequest, BrokerStatus, FirmwareEvent, Soldier, TimelineEvent

logger = logging.getLogger(__name__)
SOLDIER_TOPIC = re.compile(r"^garuda/soldiers/([A-Za-z0-9]{1,7})/(telemetry|alert|backup|location)$")
BASE_TOPICS = {"garuda/base/status", "garuda/base/confirmation"}

class InvalidFirmwareMessage(ValueError):
    pass

def parse_firmware_message(topic, raw_payload):
    try:
        payload = json.loads(raw_payload.decode("utf-8") if isinstance(raw_payload, bytes) else raw_payload)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise InvalidFirmwareMessage("Payload must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise InvalidFirmwareMessage("Payload must be a JSON object")
    match = SOLDIER_TOPIC.fullmatch(topic)
    if not match and topic not in BASE_TOPICS:
        raise InvalidFirmwareMessage("Topic is not part of the Base Station contract")
    expected = match.group(1) if match else None
    soldier_id = payload.get("soldier_id", expected)
    if expected and soldier_id != expected:
        raise InvalidFirmwareMessage("soldier_id does not match topic")
    if soldier_id is not None and not re.fullmatch(r"[A-Za-z0-9]{1,7}", str(soldier_id)):
        raise InvalidFirmwareMessage("Invalid soldier_id")
    if "event_id" not in payload:
        raise InvalidFirmwareMessage("Firmware events require event_id")
    try:
        payload["event_id"] = int(payload["event_id"])
        if payload["event_id"] < 0:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise InvalidFirmwareMessage("event_id must be a non-negative integer") from exc
    if expected and "event" not in payload:
        raise InvalidFirmwareMessage("Soldier event requires event")
    if payload.get("gps_valid") is True:
        lat, lon = payload.get("latitude"), payload.get("longitude")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            payload["gps_valid"] = False
            payload["latitude"] = payload["longitude"] = None
    return {"topic": topic, "soldier_id": soldier_id, "kind": match.group(2) if match else "base",
            "event": str(payload.get("event", "BASE_STATUS")), "payload": payload}

def _broadcast(kind, data):
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)("dashboard", {"type": "dashboard.event", "data": {"type": kind, **data}})

def process_firmware_message(topic, raw_payload):
    message = parse_firmware_message(topic, raw_payload)
    body = message["payload"]
    with transaction.atomic():
        soldier = None
        if message["soldier_id"]:
            soldier, _ = Soldier.objects.get_or_create(soldier_id=message["soldier_id"])
        try:
            with transaction.atomic():
                FirmwareEvent.objects.create(topic=topic, event_id=body["event_id"], event=message["event"], soldier=soldier, payload=body)
        except IntegrityError:
            return False  # repeated QoS 0 publish or firmware retry: apply once

        if message["kind"] == "base" and topic.endswith("/status"):
            TimelineEvent.objects.create(category="base", message=f"Base station {body.get('status', 'status unknown')}", metadata=body)
        elif message["kind"] == "base" and topic.endswith("/confirmation"):
            request = BackupRequest.objects.filter(soldier=soldier, request_id=body.get("request_id", "")).first()
            if request:
                status = body.get("status")
                if status in (BackupRequest.Status.DELIVERED, BackupRequest.Status.UNKNOWN, BackupRequest.Status.PENDING):
                    request.status = status
                    request.completed_at = timezone.now() if status == BackupRequest.Status.DELIVERED else None
                    request.save(update_fields=["status", "completed_at", "updated_at"])
                TimelineEvent.objects.create(category="backup", soldier=soldier,
                    message=f"Backup {request.request_id}: {request.get_status_display()}", metadata=body)
        elif message["kind"] == "backup":
            request, created = BackupRequest.objects.get_or_create(
                soldier=soldier, request_id=body["request_id"],
                defaults={key: body.get(key, default) for key, default in {
                    "status": BackupRequest.Status.AWAITING, "reason": "", "health_status": "",
                    "gps_valid": False, "latitude": None, "longitude": None, "rssi": None, "snr": None}.items()})
            if created:
                TimelineEvent.objects.create(category="backup", soldier=soldier,
                    message=f"Backup request {request.request_id} awaiting commander", metadata=body)
        elif soldier and message["kind"] in ("telemetry", "alert", "location"):
            fields = {k: body[k] for k in (
                "health_status", "reason", "heart_rate", "latitude", "longitude", "gps_valid", "distress", "touch",
                "adxl_ok", "lora_ok", "pulse_state", "health_risk_score", "rssi", "snr", "sequence") if k in body}
            if body.get("gps_valid") is False:
                fields["latitude"] = fields["longitude"] = None
            fields["last_seen"] = timezone.now()
            if "sequence" in fields:
                fields["last_sequence"] = fields.pop("sequence")
            for key, value in fields.items():
                setattr(soldier, key, value)
            soldier.save()
            if message["kind"] == "alert":
                TimelineEvent.objects.create(category="alert", soldier=soldier,
                    message=f"{soldier.soldier_id}: {body.get('health_status', 'ALERT')} — {body.get('reason', 'reason unavailable')}", metadata=body)
    _broadcast(message["kind"], {"soldier_id": message["soldier_id"], "payload": body})
    return True

def create_mqtt_client():
    config = settings.MQTT
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=config["CLIENT_ID"])
    if config["USERNAME"]:
        client.username_pw_set(config["USERNAME"], config["PASSWORD"])

    def record_connection(state, detail):
        BrokerStatus.objects.update_or_create(pk=1, defaults={
            "state": state, "broker_host": config["HOST"], "broker_port": config["PORT"],
            "detail": detail[:180]})

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            record_connection("CONNECTED", "Django MQTT listener is connected.")
            for topic in ("garuda/soldiers/+/telemetry", "garuda/soldiers/+/alert", "garuda/soldiers/+/backup",
                          "garuda/soldiers/+/location", "garuda/base/status", "garuda/base/confirmation"):
                client.subscribe(topic)
            logger.info("Connected to GARUDA MQTT broker and subscribed to firmware topics")
        else:
            record_connection("ERROR", f"Broker rejected connection: {reason_code}")
            logger.error("MQTT broker connection failed: %s", reason_code)

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        record_connection("DISCONNECTED", f"MQTT listener disconnected: {reason_code}")
        logger.warning("Disconnected from GARUDA MQTT broker: %s", reason_code)

    def on_message(client, userdata, msg):
        try:
            process_firmware_message(msg.topic, msg.payload)
        except InvalidFirmwareMessage as exc:
            logger.warning("Rejected MQTT message on %s: %s", msg.topic, exc)
        except Exception:
            logger.exception("Unable to process MQTT message on %s", msg.topic)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    return client

