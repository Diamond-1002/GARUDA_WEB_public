import logging
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from dashboard.mqtt_service import create_mqtt_client

class Command(BaseCommand):
    help = "Connect to the configured broker and ingest Base Station firmware events."

    def handle(self, *args, **options):
        config = settings.MQTT
        client = create_mqtt_client()
        try:
            self.stdout.write(f"Connecting to MQTT broker {config['HOST']}:{config['PORT']}...")
            client.connect(config["HOST"], config["PORT"], config["KEEPALIVE"])
            client.loop_forever()
        except KeyboardInterrupt:
            self.stdout.write("MQTT listener stopped.")
        except Exception as exc:
            raise CommandError(f"MQTT listener could not connect: {exc}") from exc

