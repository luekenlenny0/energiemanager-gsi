"""Two-step configuration of transport points, including reconfiguration."""

import voluptuous as vol

from homeassistant.config_entries import ConfigSubentryFlow
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .point_config import DATA_TYPES, KINDS, PROTOCOLS, SUBENTRY_TYPE_POINT, normalize_point


def _select(options):
    return SelectSelector(SelectSelectorConfig(options=list(options)))


def point_schema(values, step):
    """Keep protocol-specific fields together and use remembered values."""
    def req(key, default):
        return vol.Required(key, default=values.get(key, default))
    def optional(key):
        return vol.Optional(key, description={"suggested_value": values.get(key, "")})
    if step in ("user", "reconfigure"):
        return vol.Schema({req("name", "Messpunkt"): str,
                           req("protocol", "modbus"): _select(PROTOCOLS),
                           req("kind", "sensor"): _select(KINDS)})
    fields = {req("state_timeout", 30): vol.Coerce(float)}
    if values["kind"] != "switch":
        fields.update({req("unit", "W"): str, req("scale", 1): vol.Coerce(float)})
    if values["kind"] == "number":
        fields.update({req("minimum", 0): vol.Coerce(float), req("maximum", 22000): vol.Coerce(float),
                       req("step", 0.01): vol.Coerce(float)})
    if values["kind"] == "switch":
        fields.update({req("command_on", "1"): str, req("command_off", "0"): str})
    if step == "mqtt":
        fields.update({optional("state_topic"): str, optional("json_path"): str,
                       vol.Required("qos", default=str(values.get("qos", 0))): _select(["0", "1", "2"])})
        if values["kind"] != "sensor":
            fields.update({req("command_topic", ""): str, req("payload_template", "{value}"): str,
                           req("retain", False): bool})
    else:
        fields.update({req("host", ""): str, req("port", 502): vol.Coerce(float),
                       req("device_id", 1): vol.Coerce(float), req("address", 0): vol.Coerce(float),
                       req("register_type", "holding"): _select(["holding", "input", "coil", "discrete"]),
                       req("data_type", "float32"): _select(DATA_TYPES),
                       req("byte_order", "big"): _select(["big", "little"]),
                       req("word_order", "big"): _select(["big", "little"]),
                       req("poll_interval", 5): vol.Coerce(float), req("timeout", 3): vol.Coerce(float)})
        if values["kind"] != "sensor":
            fields.update({req("readback", True): bool,
                           req("write_function", "multiple"): _select(["single", "multiple"])})
    return vol.Schema(fields)


class PowerManagerPointSubentryFlow(ConfigSubentryFlow):
    """Create or edit a point without performing any device writes."""

    async def _base(self, user_input, reconfigure=False):
        self._editing = self._get_reconfigure_subentry() if reconfigure else None
        self._values = dict(self._editing.data) if self._editing else {}
        errors = {}
        if user_input is not None:
            self._values.update(user_input)
            if self._editing and any(user_input[key] != self._editing.data[key] for key in ("protocol", "kind")):
                errors["base"] = "point_type_immutable"
            elif not str(user_input.get("name", "")).strip():
                errors["base"] = "invalid_point"
            elif user_input.get("protocol") in PROTOCOLS and user_input.get("kind") in KINDS:
                return await self._protocol(None, self._values["protocol"])
            else:
                errors["base"] = "invalid_point"
        step = "reconfigure" if reconfigure else "user"
        return self.async_show_form(step_id=step, data_schema=point_schema(self._values, step), errors=errors)

    async def async_step_user(self, user_input=None):
        return await self._base(user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._base(user_input, True)

    async def _protocol(self, user_input, protocol):
        errors, detail = {}, ""
        if user_input is not None:
            # Clear optional fields removed from the reconfiguration form.
            for key in ("state_topic", "json_path"):
                if protocol == "mqtt":
                    self._values[key] = ""
            self._values.update(user_input)
            try:
                normalized = normalize_point(self._values)
                for key, sub in self._get_entry().subentries.items():
                    if self._editing and key == self._editing.subentry_id:
                        continue
                    if sub.subentry_type != SUBENTRY_TYPE_POINT:
                        continue
                    other = normalize_point(dict(sub.data))
                    if other["name"].casefold() == normalized["name"].casefold():
                        raise ValueError("A point with this name already exists")
                    # Two writable point entities must never address the same output.
                    if normalized["kind"] != "sensor" and other["kind"] != "sensor" and other["protocol"] == protocol:
                        keys = ("command_topic",) if protocol == "mqtt" else ("host", "port", "device_id", "register_type")
                        if all(other[key] == normalized[key] for key in keys):
                            from .modbus_tcp import register_count
                            if protocol == "mqtt" or (
                                normalized["address"] < other["address"] + (1 if other["register_type"] == "coil" else register_count(other))
                                and other["address"] < normalized["address"] + (1 if normalized["register_type"] == "coil" else register_count(normalized))
                            ):
                                raise ValueError("This output overlaps an existing point")
                if self._editing:
                    return self.async_update_and_abort(self._get_entry(), self._editing,
                                                       title=normalized["name"], data=normalized)
                return self.async_create_entry(title=normalized["name"], data=normalized)
            except (ValueError, TypeError, OverflowError) as err:
                errors["base"], detail = "invalid_point", str(err)
        return self.async_show_form(step_id=protocol, data_schema=point_schema(self._values, protocol),
                                    errors=errors, description_placeholders={"detail": detail})

    async def async_step_mqtt(self, user_input=None):
        return await self._protocol(user_input, "mqtt")

    async def async_step_modbus(self, user_input=None):
        return await self._protocol(user_input, "modbus")
