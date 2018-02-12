"""
Support for Unifi WAP controllers.
"""
import logging
import datetime
import time
from datetime import timedelta
import os
from threading import Thread
import json
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8443
DEFAULT_VERIFY_SSL = False
DEFAULT_REFRESH_TIME = 15
DEFAULT_DETECTION_TIME = 180

def get_scanner():
    """Set up the Unifi device_tracker."""
    from pyunifi.controller import Controller

    ctrl = Controller(os.environ.get('UNIFI_HOST', DEFAULT_HOST), os.environ['UNIFI_USERNAME'], os.environ['UNIFI_PASSWORD'], os.environ.get('UNIFI_PORT', DEFAULT_PORT), version='v4',
          site_id=os.environ.get('UNIFI_SITE_ID', "default"), ssl_verify=DEFAULT_VERIFY_SSL)

    if os.environ.get('DETECTION_TIME', None) is None:
        detection_time = DEFAULT_DETECTION_TIME
    else:
        detection_time = int(os.environ['DETECTION_TIME'])

    return UnifiScanner(ctrl, timedelta(seconds=detection_time))


class UnifiScanner:
    """Provide device_tracker support from Unifi WAP client data."""

    def __init__(self, controller, detection_time):
        """Initialize the scanner."""
        self._detection_time = detection_time
        self._controller = controller
        self._present = set()
        self._update()

    def _update(self):
        """Get the clients from the device."""
        from pyunifi.controller import APIError
        try:
            clients = self._controller.get_clients()
        except APIError as ex:
            _LOGGER.error("Failed to scan clients: %s", ex)
            clients = []


        self._all_clients = {
            client['mac']: client
            for client in clients
        }

        self._clients = {
            client['mac']: client
            for client in clients
            if (datetime.datetime.utcnow() - datetime.datetime.fromtimestamp(float(client['last_seen']))) < self._detection_time}

    def get_diff(self):
        new_devices = set(self.scan_devices())

        # Disappeared
        gone = self._present - new_devices
        appeared = new_devices - self._present

        self._present = new_devices

        return gone, appeared

    def scan_devices(self):
        """Scan for devices."""
        self._update()
        return self._clients.keys()

    def get_device_name(self, mac):
        """Return the name (if known) of the device.

        If a name has been set in Unifi, then return that, else
        return the hostname if it has been detected.
        """
        client = self._all_clients.get(mac, {})
        name = client.get('name') or client.get('hostname')
        _LOGGER.debug("Device mac %s name %s", mac, name)
        return name

def refresh_loop(client):
    scanner = get_scanner()

    while True:
        gone, appeared = scanner.get_diff()

        out = []
        for mac in gone:
            data = { 'type': 'disappear', 'mac': mac, 'hostname': scanner.get_device_name(mac) }
            out.append(data)

        for mac in appeared:
            data = { 'type': 'appear', 'mac': mac, 'hostname': scanner.get_device_name(mac) }
            out.append(data)

        for data in out:
            msg = json.dumps(data)
            print msg
            client.publish(os.environ['MQTT_TOPIC'], msg)

        time.sleep(DEFAULT_REFRESH_TIME)

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT with result code "+str(rc))

client = mqtt.Client()
client.on_connect = on_connect

if os.environ.get('MQTT_PORT', None) is None:
    port = 1883
else:
    port = int(os.environ['MQTT_PORT'])

client.connect(os.environ['MQTT_BROKER'], port, 60)

t = Thread(target=refresh_loop, args=(client,))
t.start()

client.loop_forever()