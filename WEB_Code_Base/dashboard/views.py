import json
import uuid
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import BackupRequest, BrokerStatus, Soldier, TimelineEvent
from .mqtt_service import create_mqtt_client
from .serializers import BackupRequestSerializer, SoldierSerializer, TimelineSerializer

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    error = ""
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("username", ""), password=request.POST.get("password", ""))
        if user and user.is_active:
            login(request, user)
            return redirect(request.GET.get("next") or "dashboard")
        error = "Sign-in failed. Check your username and password."
    return render(request, "dashboard/login.html", {"error": error})

def logout_view(request):
    logout(request)
    return redirect("login")

@login_required(login_url="login")
def dashboard(request):
    return render(request, "dashboard/index.html", {"commander": request.user})

@api_view(["GET"])
def broker_status(request):
    current = BrokerStatus.objects.filter(pk=1).first()
    if not current:
        return Response({"state": "UNKNOWN", "broker_host": settings.MQTT["HOST"],
                         "broker_port": settings.MQTT["PORT"], "detail": "MQTT listener has not reported a connection."})
    return Response({"state": current.state, "broker_host": current.broker_host,
                     "broker_port": current.broker_port, "detail": current.detail,
                     "updated_at": current.updated_at})


class SoldierViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Soldier.objects.all().order_by("soldier_id")
    serializer_class = SoldierSerializer

    @action(detail=False, methods=["get"])
    def timeline(self, request):
        events = TimelineEvent.objects.select_related("soldier")[:60]
        return Response(TimelineSerializer(events, many=True).data)

class BackupRequestViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BackupRequest.objects.select_related("soldier").all()
    serializer_class = BackupRequestSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        backup = self.get_object()
        if backup.status != BackupRequest.Status.AWAITING:
            return Response({"detail": f"Request is {backup.status}; only an awaiting request can be confirmed."}, status=status.HTTP_409_CONFLICT)
        command_id = "CMD" + uuid.uuid4().hex[:12].upper()
        payload = json.dumps({"command": "COMMANDER_CONFIRMED", "soldier_id": backup.soldier.soldier_id,
                              "request_id": backup.request_id, "command_id": command_id})
        client = create_mqtt_client()
        try:
            client.connect(settings.MQTT["HOST"], settings.MQTT["PORT"], settings.MQTT["KEEPALIVE"])
            client.loop_start()
            info = client.publish("garuda/base/commands", payload, qos=0)
            info.wait_for_publish(timeout=3)
            if not info.is_published():
                return Response({"detail": "MQTT command was not accepted for publishing."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            return Response({"detail": f"MQTT publish failed: {exc}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        finally:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass
        backup.status = BackupRequest.Status.PENDING
        backup.command_id = command_id
        backup.commander_confirmed_at = timezone.now()
        backup.save(update_fields=["status", "command_id", "commander_confirmed_at", "updated_at"])
        TimelineEvent.objects.create(category="backup", soldier=backup.soldier,
            message=f"Commander confirmation sent for {backup.request_id}; awaiting soldier acknowledgement",
            metadata={"request_id": backup.request_id, "command_id": command_id})
        return Response(BackupRequestSerializer(backup).data)

