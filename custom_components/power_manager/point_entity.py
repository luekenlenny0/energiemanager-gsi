"""Native HA entities backed by directly configured transport points."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .point_config import write_only


class PointEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = None

    def __init__(self, manager, key):
        self.manager, self.key = manager, key
        self.point = manager.points[key]
        self.config = self.point.config
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}_io_point"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{manager.entry.entry_id}:point:{key}")},
            name=self.config["name"], manufacturer="GSI",
            model="Modbus TCP" if self.config["protocol"] == "modbus" else "MQTT",
        )
        self._attr_assumed_state = write_only(self.config)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.point.listeners.add(self.async_write_ha_state)
        self.async_on_remove(lambda: self.point.listeners.discard(self.async_write_ha_state))

    @property
    def available(self):
        return self.point.available

    @property
    def extra_state_attributes(self):
        c = self.config
        return {"power_manager_point": True, "power_manager_entry_id": self.manager.entry.entry_id,
                "power_manager_write_only": write_only(c), "protocol": c["protocol"],
                "point_kind": c["kind"], "point_error": self.point.error,
                "endpoint": f"{c['host']}:{c['port']} / ID {c['device_id']} / {c['register_type']} {c['address']}"
                if c["protocol"] == "modbus" else c["state_topic"] or c["command_topic"]}


class PointSensor(PointEntity, SensorEntity):
    # Repeated equal meter readings are still fresh physical measurements.
    _attr_force_update = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, key):
        super().__init__(manager, key)
        self._attr_native_unit_of_measurement = self.config["unit"] or None
        self._attr_device_class = {"W": SensorDeviceClass.POWER, "kW": SensorDeviceClass.POWER,
                                   "MW": SensorDeviceClass.POWER, "A": SensorDeviceClass.CURRENT,
                                   "V": SensorDeviceClass.VOLTAGE}.get(self.config["unit"])

    @property
    def native_value(self):
        return self.point.value


class PointNumber(PointEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, manager, key):
        super().__init__(manager, key)
        self._attr_native_unit_of_measurement = self.config["unit"] or None
        self._attr_native_min_value = self.config["minimum"]
        self._attr_native_max_value = self.config["maximum"]
        self._attr_native_step = self.config["step"]

    @property
    def native_value(self):
        return self.point.value

    async def async_set_native_value(self, value):
        await self.manager.write(self.key, value)


class PointSwitch(PointEntity, SwitchEntity):
    @property
    def is_on(self):
        return self.point.value

    async def async_turn_on(self, **kwargs):
        await self.manager.write(self.key, True)

    async def async_turn_off(self, **kwargs):
        await self.manager.write(self.key, False)


def add_point_entities(entry, kind, async_add_entities):
    manager = entry.runtime_data.direct_io
    entity_class = {"sensor": PointSensor, "number": PointNumber, "switch": PointSwitch}[kind]
    for key, point in manager.points.items():
        if point.config["kind"] == kind:
            async_add_entities([entity_class(manager, key)], config_subentry_id=key)
