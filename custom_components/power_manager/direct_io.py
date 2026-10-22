"""Lifecycle and state for directly configured MQTT and Modbus points."""

import asyncio
from dataclasses import dataclass, field
from math import isfinite
from time import monotonic

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .modbus_tcp import ModbusTCPClient
from .point_config import SUBENTRY_TYPE_POINT, normalize_point, parse_payload, write_only


@dataclass
class PointState:
    config: dict
    value: float | bool | None = None
    available: bool = False
    error: str | None = None
    updated: float | None = None
    listeners: set = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    connection_generation: int = -1

    def notify(self):
        for listener in tuple(self.listeners):
            listener()


class DirectIO:
    """Own all subscriptions, polls and shared TCP clients for an entry."""

    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.points = {key: PointState(normalize_point(dict(sub.data)))
                       for key, sub in entry.subentries.items() if sub.subentry_type == SUBENTRY_TYPE_POINT}
        self.clients = {}
        self.tasks = []
        self.unsubscribers = []
        self.mqtt_subscribed = set()
        self.mqtt = None
        self.stopped = False

    def start(self):
        for key, point in self.points.items():
            self.tasks.append(self.hass.async_create_background_task(
                self._run(key, point), f"GSI {point.config['protocol']} {key}"))

    async def stop(self):
        self.stopped = True
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        for unsubscribe in self.unsubscribers:
            unsubscribe()
        for client in self.clients.values():
            await client.close()

    def client(self, config):
        endpoint = config["host"], config["port"]
        if endpoint not in self.clients:
            self.clients[endpoint] = ModbusTCPClient(*endpoint)
        return self.clients[endpoint]

    def _set_value(self, point, value):
        point.value, point.available, point.error = value, True, None
        point.updated = monotonic()
        point.notify()

    def _set_error(self, point, error):
        point.available, point.error = False, str(error)
        if write_only(point.config):
            point.value = None
        point.notify()

    def mqtt_connected(self):
        try:
            return bool(self.mqtt and self.mqtt.is_connected(self.hass))
        except (KeyError, AttributeError):
            return False

    @callback
    def _connection_changed(self, connected):
        for point in self.points.values():
            if point.config["protocol"] != "mqtt":
                continue
            # After reconnect, measurements require a new non-retained message.
            point.updated = None
            if write_only(point.config):
                point.value = None
            point.available = bool(connected and write_only(point.config))
            point.error = None if point.available else "MQTT: waiting for fresh state" if connected else "MQTT disconnected"
            point.notify()

    async def _setup_mqtt(self, key, point):
        if self.mqtt is None:
            from homeassistant.components import mqtt
            self.mqtt = mqtt
            self.unsubscribers.append(mqtt.async_subscribe_connection_status(self.hass, self._connection_changed))
        if key in self.mqtt_subscribed:
            return
        config = point.config
        if config["state_topic"]:
            @callback
            def message_received(message):
                if self.stopped:
                    return
                try:
                    if message.retain:
                        raise ValueError("Retained state ignored; waiting for a fresh device measurement")
                    self._set_value(point, parse_payload(message.payload, config))
                except (ValueError, TypeError, KeyError, IndexError) as err:
                    self._set_error(point, err)
            self.unsubscribers.append(await self.mqtt.async_subscribe(
                self.hass, config["state_topic"], message_received, qos=config["qos"]))
        self.mqtt_subscribed.add(key)

    async def _run(self, key, point):
        config = point.config
        while not self.stopped:
            try:
                if config["protocol"] == "mqtt":
                    await self._setup_mqtt(key, point)
                    if not self.mqtt_connected():
                        raise HomeAssistantError("MQTT broker not configured or disconnected")
                    if write_only(config):
                        point.available, point.error = True, None
                        point.notify()
                    elif point.updated is None or monotonic() - point.updated > config["state_timeout"]:
                        raise HomeAssistantError("MQTT: no fresh state within configured timeout")
                else:
                    # Serialize a point's reads and writes so an older poll can
                    # never overwrite the state of a newer command.
                    async with point.lock:
                        if write_only(config):
                            client = self.client(config)
                            await client.connect(config["timeout"])
                            if point.connection_generation != client.generation:
                                point.value = None
                                point.connection_generation = client.generation
                            point.available, point.error = True, None
                            point.notify()
                        else:
                            self._set_value(point, await self.client(config).read(config))
            except asyncio.CancelledError:
                raise
            except (HomeAssistantError, OSError, RuntimeError, ValueError, KeyError, ImportError) as err:
                self._set_error(point, err)
            await asyncio.sleep(min(1.0, config["state_timeout"] / 2) if config["protocol"] == "mqtt" else config["poll_interval"])

    async def write(self, key, value):
        point = self.points[key]
        config = point.config
        if self.stopped or config["kind"] == "sensor":
            raise HomeAssistantError("Point is read-only or stopped")
        if config["kind"] == "number":
            value = float(value)
            if not isfinite(value) or not config["minimum"] <= value <= config["maximum"]:
                raise HomeAssistantError("Setpoint outside configured point limits")
        async with point.lock:
            try:
                if config["protocol"] == "mqtt":
                    if not self.mqtt_connected():
                        raise HomeAssistantError("MQTT broker disconnected")
                    raw = config["command_on"] if value else config["command_off"]
                    if config["kind"] == "number":
                        native = value / config["scale"]
                        if not isfinite(native):
                            raise ValueError("Scaled MQTT setpoint is not finite")
                        raw = format(native, ".15g")
                    payload = config["payload_template"].replace("{value}", str(raw))
                    await self.mqtt.async_publish(self.hass, config["command_topic"], payload,
                                                  qos=config["qos"], retain=config["retain"])
                else:
                    await self.client(config).write(config, value)
                if write_only(config):
                    self._set_value(point, value)
                # A readback point only changes on an actual response/message.
                # In particular, issuing a command never refreshes its meter age.
            except (HomeAssistantError, OSError, RuntimeError, ValueError) as err:
                self._set_error(point, err)
                raise HomeAssistantError(f"{config['name']}: {err}") from err
