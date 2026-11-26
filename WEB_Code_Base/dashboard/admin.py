from django.contrib import admin
from .models import BackupRequest, BrokerStatus, FirmwareEvent, Soldier, TimelineEvent

@admin.register(Soldier)
class SoldierAdmin(admin.ModelAdmin):
    list_display = ("soldier_id", "health_status", "last_seen", "distress")
    search_fields = ("soldier_id",)

@admin.register(BackupRequest)
class BackupRequestAdmin(admin.ModelAdmin):
    list_display = ("soldier", "request_id", "status", "created_at")
    list_filter = ("status",)

admin.site.register(FirmwareEvent)
admin.site.register(TimelineEvent)


admin.site.register(BrokerStatus)
