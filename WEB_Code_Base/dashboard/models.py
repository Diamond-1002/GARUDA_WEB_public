from django.db import models

class Soldier(models.Model):
    soldier_id = models.CharField(max_length=7, unique=True)
    health_status = models.CharField(max_length=16, blank=True, default="")
    reason = models.CharField(max_length=80, blank=True, default="")
    heart_rate = models.IntegerField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    gps_valid = models.BooleanField(default=False)
    distress = models.BooleanField(default=False)
    touch = models.BooleanField(default=False)
    adxl_ok = models.BooleanField(null=True, blank=True)
    lora_ok = models.BooleanField(null=True, blank=True)
    pulse_state = models.CharField(max_length=16, blank=True, default="")
    health_risk_score = models.IntegerField(null=True, blank=True)
    rssi = models.IntegerField(null=True, blank=True)
    snr = models.FloatField(null=True, blank=True)
    last_sequence = models.BigIntegerField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.soldier_id

class BackupRequest(models.Model):
    class Status(models.TextChoices):
        AWAITING = "SEEN_AWAITING_COMMANDER", "Awaiting commander"
        PENDING = "PENDING", "Commander confirmed, awaiting soldier"
        DELIVERED = "CONFIRMED_DELIVERED", "Confirmed by soldier"
        UNKNOWN = "DELIVERY_UNKNOWN", "Delivery unknown"

    request_id = models.CharField(max_length=15)
    soldier = models.ForeignKey(Soldier, on_delete=models.CASCADE, related_name="backup_requests")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.AWAITING)
    command_id = models.CharField(max_length=15, blank=True, default="")
    reason = models.CharField(max_length=80, blank=True, default="")
    health_status = models.CharField(max_length=16, blank=True, default="")
    gps_valid = models.BooleanField(default=False)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    rssi = models.IntegerField(null=True, blank=True)
    snr = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    commander_confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["soldier", "request_id"], name="unique_soldier_backup_request")]
        ordering = ["-created_at"]

class FirmwareEvent(models.Model):
    topic = models.CharField(max_length=120)
    event_id = models.PositiveBigIntegerField()
    event = models.CharField(max_length=32)
    soldier = models.ForeignKey(Soldier, null=True, blank=True, on_delete=models.SET_NULL)
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["topic", "event_id"], name="unique_firmware_event")]
        ordering = ["-received_at"]

class TimelineEvent(models.Model):
    category = models.CharField(max_length=32)
    message = models.CharField(max_length=180)
    soldier = models.ForeignKey(Soldier, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]




class BrokerStatus(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    state = models.CharField(max_length=16, default="UNKNOWN")
    broker_host = models.CharField(max_length=120, blank=True, default="")
    broker_port = models.PositiveIntegerField(default=1883)
    detail = models.CharField(max_length=180, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "MQTT broker status"

