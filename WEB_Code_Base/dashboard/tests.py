import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import BackupRequest, FirmwareEvent, Soldier, TimelineEvent
from .mqtt_service import InvalidFirmwareMessage, parse_firmware_message, process_firmware_message

class FirmwareContractTests(TestCase):
    def setUp(self):
        # Tests exercise persistence and firmware flow; the ASGI broadcast is
        # covered by the Channels consumer and needs no running event loop here.
        self.broadcast_patch = patch("dashboard.mqtt_service._broadcast")
        self.broadcast_patch.start()
        self.addCleanup(self.broadcast_patch.stop)

    def test_parses_contract_telemetry_and_sanitizes_invalid_gps(self):
        msg = parse_firmware_message("garuda/soldiers/S01/telemetry", json.dumps({
            "event": "TELEM", "event_id": 9, "soldier_id": "S01", "gps_valid": True,
            "latitude": 100, "longitude": 181, "health_status": "WATCH"}))
        self.assertEqual(msg["kind"], "telemetry")
        self.assertFalse(msg["payload"]["gps_valid"])
        self.assertIsNone(msg["payload"]["latitude"])

    def test_rejects_non_contract_topic_and_wrong_soldier(self):
        with self.assertRaises(InvalidFirmwareMessage):
            parse_firmware_message("garuda/soldiers/S01/telemetry", '{"event":"TELEM","event_id":1,"soldier_id":"S02"}')
        with self.assertRaises(InvalidFirmwareMessage):
            parse_firmware_message("garuda/unknown", '{"event_id":1}')

    def test_deduplicates_by_topic_and_firmware_event_id(self):
        payload = {"event": "TELEM", "event_id": 4, "soldier_id": "S01", "heart_rate": 81, "health_status": "SAFE"}
        self.assertTrue(process_firmware_message("garuda/soldiers/S01/telemetry", json.dumps(payload)))
        payload["heart_rate"] = 99
        self.assertFalse(process_firmware_message("garuda/soldiers/S01/telemetry", json.dumps(payload)))
        self.assertEqual(FirmwareEvent.objects.count(), 1)
        self.assertEqual(Soldier.objects.get(soldier_id="S01").heart_rate, 81)

    @patch("dashboard.views.create_mqtt_client")
    def test_commander_confirmation_publishes_exact_firmware_command_and_waits_for_ack(self, create_client):
        user = get_user_model().objects.create_user(username="commander", password="pass")
        soldier = Soldier.objects.create(soldier_id="S01")
        backup = BackupRequest.objects.create(soldier=soldier, request_id="REQ001", status=BackupRequest.Status.AWAITING)
        mock = create_client.return_value
        mock.publish.return_value.is_published.return_value = True
        api = APIClient()
        api.force_authenticate(user)
        response = api.post(f"/api/backup-requests/{backup.pk}/confirm/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        topic, raw_command = mock.publish.call_args.args[:2]
        command = json.loads(raw_command)
        self.assertEqual(topic, "garuda/base/commands")
        self.assertEqual({k: command[k] for k in ("command", "soldier_id", "request_id")},
                         {"command": "COMMANDER_CONFIRMED", "soldier_id": "S01", "request_id": "REQ001"})
        backup.refresh_from_db()
        self.assertEqual(backup.status, BackupRequest.Status.PENDING)
        self.assertTrue(backup.command_id.startswith("CMD"))
        self.assertIsNone(backup.completed_at)

    def test_confirmation_status_topic_completes_or_marks_unknown(self):
        soldier = Soldier.objects.create(soldier_id="S01")
        backup = BackupRequest.objects.create(soldier=soldier, request_id="REQ001", status=BackupRequest.Status.PENDING)
        for event_id, status in ((1, "CONFIRMED_DELIVERED"),):
            process_firmware_message("garuda/base/confirmation", json.dumps({"event": "CONFIRMATION", "event_id": event_id,
                "soldier_id": "S01", "request_id": "REQ001", "command_id": "CMD001", "status": status}))
        backup.refresh_from_db()
        self.assertEqual(backup.status, BackupRequest.Status.DELIVERED)
        self.assertIsNotNone(backup.completed_at)

    def test_delivery_unknown_does_not_claim_success(self):
        soldier = Soldier.objects.create(soldier_id="S01")
        backup = BackupRequest.objects.create(soldier=soldier, request_id="REQ001", status=BackupRequest.Status.PENDING)
        process_firmware_message("garuda/base/confirmation", json.dumps({"event": "CONFIRMATION", "event_id": 2,
            "soldier_id": "S01", "request_id": "REQ001", "command_id": "CMD001", "status": "DELIVERY_UNKNOWN"}))
        backup.refresh_from_db()
        self.assertEqual(backup.status, BackupRequest.Status.UNKNOWN)
        self.assertIsNone(backup.completed_at)

