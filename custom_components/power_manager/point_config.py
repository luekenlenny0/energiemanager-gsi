"""Validated, transport-independent configuration for direct I/O points."""

from math import isfinite

SUBENTRY_TYPE_POINT = "point"
PROTOCOLS = ("modbus", "mqtt")
KINDS = ("sensor", "number", "switch")
DATA_TYPES = {"uint16": "H", "int16": "h", "uint32": "I", "int32": "i", "float32": "f", "float64": "d"}


def normalize_point(data):
    """Reject invalid settings before any subscription or network operation."""
    value = {"name": "Messpunkt", "protocol": "modbus", "kind": "sensor",
             "unit": "W", "scale": 1.0, "state_timeout": 30.0,
             "minimum": 0.0, "maximum": 22000.0, "step": 0.01,
             "host": "", "port": 502, "device_id": 1, "address": 0,
             "register_type": "holding", "data_type": "float32",
             "byte_order": "big", "word_order": "big", "poll_interval": 5.0,
             "timeout": 3.0, "readback": True, "write_function": "multiple",
             "state_topic": "", "command_topic": "", "json_path": "",
             "payload_template": "{value}", "qos": 0, "retain": False,
             "command_on": "1", "command_off": "0", **data}
    for key in ("name", "host", "state_topic", "command_topic", "json_path", "unit"):
        value[key] = str(value[key]).strip()
    for key in ("command_on", "command_off", "payload_template"):
        value[key] = str(value[key])
    for key in ("scale", "state_timeout", "minimum", "maximum", "step", "poll_interval", "timeout"):
        value[key] = float(value[key])
        if not isfinite(value[key]):
            raise ValueError(f"{key}: finite number required")
    for key in ("port", "device_id", "address", "qos"):
        number = float(value[key])
        if not isfinite(number) or not number.is_integer():
            raise ValueError(f"{key}: integer required")
        value[key] = int(number)
    if not value["name"] or value["protocol"] not in PROTOCOLS or value["kind"] not in KINDS:
        raise ValueError("Name, protocol or kind invalid")
    if value["scale"] <= 0 or value["state_timeout"] < 1 or value["step"] <= 0:
        raise ValueError("Scale, timeout and step must be positive")
    if value["minimum"] >= value["maximum"]:
        raise ValueError("Minimum must be below maximum")
    if value["command_on"] == value["command_off"]:
        raise ValueError("ON and OFF must differ")
    if value["protocol"] == "mqtt":
        if value["qos"] not in (0, 1, 2):
            raise ValueError("Invalid QoS")
        if value["kind"] == "sensor" and not value["state_topic"]:
            raise ValueError("State topic required")
        if value["kind"] != "sensor" and not value["command_topic"]:
            raise ValueError("Command topic required")
        for key in ("state_topic", "command_topic"):
            topic = value[key]
            if any(char in topic for char in ("#", "+", "\0")) or len(topic.encode("utf-8")) > 65535:
                raise ValueError("Use a concrete MQTT topic without wildcards")
        if value["kind"] != "sensor" and "{value}" not in value["payload_template"]:
            raise ValueError("Payload template requires {value}")
    else:
        if not value["host"] or not 1 <= value["port"] <= 65535 or not 0 <= value["device_id"] <= 255:
            raise ValueError("Invalid Modbus endpoint")
        if value["register_type"] not in ("holding", "input", "coil", "discrete"):
            raise ValueError("Invalid register type")
        if value["data_type"] not in DATA_TYPES:
            raise ValueError("Invalid data type")
        if value["byte_order"] not in ("big", "little") or value["word_order"] not in ("big", "little"):
            raise ValueError("Invalid byte/word order")
        if value["poll_interval"] < 1 or value["timeout"] < 0.1 or value["timeout"] > 30:
            raise ValueError("Invalid poll interval or timeout")
        if value["state_timeout"] < value["poll_interval"] + value["timeout"]:
            raise ValueError("State timeout must cover polling interval plus request timeout")
        if value["kind"] != "sensor" and value["register_type"] not in ("holding", "coil"):
            raise ValueError("Outputs require holding registers or coils")
        if value["kind"] == "number" and value["register_type"] == "coil":
            raise ValueError("Coils require a switch")
        if value["kind"] == "switch" and value["register_type"] == "coil" and (
            value["command_on"] != "1" or value["command_off"] != "0"
        ):
            raise ValueError("Coils use ON=1 and OFF=0; custom codes require a holding register")
        if value["kind"] == "sensor" and value["register_type"] in ("coil", "discrete"):
            # Numeric 0/1 sensor, never a power value unless deliberately mapped.
            value["unit"] = ""
        count = {"uint16": 1, "int16": 1, "uint32": 2, "int32": 2, "float32": 2, "float64": 4}[value["data_type"]]
        if value["register_type"] in ("coil", "discrete"):
            count = 1
        if not 0 <= value["address"] <= 65536 - count:
            raise ValueError("Register address outside 0..65535")
        if value["write_function"] not in ("single", "multiple"):
            raise ValueError("Invalid write function")
        if value["kind"] != "sensor" and value["register_type"] == "holding":
            from .modbus_tcp import encode_registers
            if value["write_function"] == "single" and count != 1:
                raise ValueError("FC6 can only write one 16-bit register")
            if value["kind"] == "switch":
                if float(value["command_on"]) == float(value["command_off"]):
                    raise ValueError("Numeric ON and OFF values must differ")
                encoded_on = encode_registers(float(value["command_on"]), value)
                encoded_off = encode_registers(float(value["command_off"]), value)
                if encoded_on == encoded_off:
                    raise ValueError("ON and OFF encode to the same register value")
            else:
                encode_registers(value["minimum"], value)
                encode_registers(value["maximum"], value)
    return value


def write_only(config):
    return config["kind"] != "sensor" and (
        not config["state_topic"] if config["protocol"] == "mqtt" else not config["readback"]
    )


def parse_payload(payload, config):
    """Extract numeric state or exact ON/OFF payload, without executing templates."""
    import json
    result = payload
    if config["json_path"]:
        result = json.loads(payload)
        for part in config["json_path"].split("."):
            result = result[int(part)] if isinstance(result, list) else result[part]
    if config["kind"] == "switch":
        text = str(result)
        if text == str(config["command_on"]):
            return True
        if text == str(config["command_off"]):
            return False
        raise ValueError("Unknown switch payload")
    if isinstance(result, bool):
        raise ValueError("Boolean payload is not a numeric measurement")
    number = float(result) * config["scale"]
    if not isfinite(number):
        raise ValueError("Non-finite measurement")
    return number
