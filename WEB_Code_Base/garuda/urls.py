from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from dashboard.views import BackupRequestViewSet, SoldierViewSet, broker_status, dashboard, login_view, logout_view

router = DefaultRouter()
router.register("soldiers", SoldierViewSet, basename="soldier")
router.register("backup-requests", BackupRequestViewSet, basename="backup-request")

urlpatterns = [
    path("admin/", admin.site.urls), path("api/", include(router.urls)),
    path("api/broker-status/", broker_status, name="broker-status"),
    path("login/", login_view, name="login"), path("logout/", logout_view, name="logout"),
    path("", dashboard, name="dashboard"),
]

