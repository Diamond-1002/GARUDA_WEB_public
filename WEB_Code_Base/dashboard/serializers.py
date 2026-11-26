from django.utils import timezone
from rest_framework import serializers
from .models import BackupRequest, Soldier, TimelineEvent
from django.conf import settings

class SoldierSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    def get_status(self, obj):
        if not obj.last_seen:
            return "UNKNOWN"
        if (timezone.now() - obj.last_seen).total_seconds() > settings.DEVICE_OFFLINE_SECONDS:
            return "OFFLINE"
        return obj.health_status or "UNKNOWN"
    class Meta:
        model = Soldier
        fields = ["soldier_id", "status", "health_status", "reason", "heart_rate", "latitude", "longitude",
                  "gps_valid", "distress", "touch", "adxl_ok", "lora_ok", "pulse_state", "health_risk_score",
                  "rssi", "snr", "last_sequence", "last_seen"]

class BackupRequestSerializer(serializers.ModelSerializer):
    soldier_id = serializers.CharField(source="soldier.soldier_id", read_only=True)
    class Meta:
        model = BackupRequest
        fields = ["id", "soldier_id", "request_id", "status", "command_id", "reason", "health_status",
                  "gps_valid", "latitude", "longitude", "rssi", "snr", "created_at", "commander_confirmed_at", "completed_at"]

class TimelineSerializer(serializers.ModelSerializer):
    soldier_id = serializers.CharField(source="soldier.soldier_id", read_only=True)
    class Meta:
        model = TimelineEvent
        fields = ["id", "category", "message", "soldier_id", "created_at", "metadata"]

