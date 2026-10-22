"""Protocol tests use a real local TCP server and a broker API double."""

import asyncio
import importlib
from math import nan
import struct
import sys
from types import ModuleType, SimpleNamespace

import pytest

from custom_components.power_manager.modbus_tcp import ModbusTCPClient, ModbusError, decode_registers, encode_registers
from custom_components.power_manager.point_config import normalize_point, parse_payload, write_only


def config(**values):
    return normalize_point({"host": "127.0.0.1", **values})


@pytest.mark.parametrize("dtype,value", [("uint16", 65000), ("int16", -120), ("uint32", 4000000000),
    ("int32", -200000), ("float32", 12.25), ("float64", -12.123456)])
@pytest.mark.parametrize("byte_order,word_order", [("big", "big"), ("little", "big"), ("big", "little"), ("little", "little")])
def test_codec_round_trip(dtype, value, byte_order, word_order):
    c = config(data_type=dtype, byte_order=byte_order, word_order=word_order, scale=0.01)
    assert decode_registers(encode_registers(value * 0.01, c), c) == pytest.approx(value * 0.01)


def test_codec_has_known_wire_order_and_rejects_unrepresentable_writes():
    assert encode_registers(0x12345678, config(data_type="uint32")) == bytes.fromhex("12345678")
    assert encode_registers(0x12345678, config(data_type="uint32", word_order="little")) == bytes.fromhex("56781234")
    assert encode_registers(0x12345678, config(data_type="uint32", byte_order="little")) == bytes.fromhex("34127856")
    for value in (nan, 65536, -1, 12.5):
        with pytest.raises(ValueError):
            encode_registers(value, config(data_type="uint16"))


@pytest.mark.parametrize("values", [dict(port=0), dict(port=502.5), dict(device_id=256), dict(address=65535),
    dict(scale=0), dict(scale=nan), dict(state_timeout=2), dict(kind="number", register_type="input"),
    dict(kind="number", write_function="single"), dict(kind="switch", command_on="12", command_off="12"),
    dict(protocol="mqtt", state_topic="test/#"), dict(protocol="mqtt", state_topic=""),
    dict(protocol="mqtt", kind="number", command_topic="test/set", payload_template="fixed"),
    dict(kind="switch", data_type="uint16", command_on="65536")])
def test_invalid_configuration_never_reaches_network(values):
    with pytest.raises((ValueError, OverflowError)):
        config(**values)


@pytest.mark.parametrize("values", [dict(command_on="12", command_off="12.0"),
    dict(command_on="12", command_off="12.00000001"),
    dict(register_type="coil", command_on="12", command_off="14")])
def test_switch_codes_must_remain_distinct_on_the_wire(values):
    with pytest.raises(ValueError):
        config(kind="switch", **values)


def test_mqtt_paths_scale_and_custom_payloads():
    c = config(protocol="mqtt", state_topic="meter", json_path="values.0.power", scale=.1)
    assert parse_payload('{"values":[{"power":1234}]}', c) == 123.4
    c = config(protocol="mqtt", kind="switch", state_topic="state", command_topic="set", command_on="12", command_off="14")
    assert parse_payload("12", c) is True
    assert parse_payload("14", c) is False
    with pytest.raises(ValueError):
        parse_payload("1", c)
    c = config(protocol="mqtt", state_topic="meter")
    with pytest.raises(ValueError):
        parse_payload("NaN", c)


async def with_server(handler, exercise):
    tasks = set()
    async def connection(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        try:
            while True:
                header = await reader.readexactly(7)
                tid, proto, size, unit = struct.unpack(">HHHB", header)
                pdu = await reader.readexactly(size - 1)
                reply = await handler(tid, unit, pdu)
                if reply is None:
                    break
                out_tid, out_unit, out_pdu = reply
                writer.write(struct.pack(">HHHB", out_tid, 0, len(out_pdu) + 1, out_unit) + out_pdu)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError, asyncio.CancelledError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.discard(task)
    server = await asyncio.start_server(connection, "127.0.0.1", 0)
    client = ModbusTCPClient("127.0.0.1", server.sockets[0].getsockname()[1])
    try:
        await exercise(client)
    finally:
        await client.close()
        server.close()
        await server.wait_closed()
        for task in tuple(tasks):
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def test_tcp_reads_writes_registers_coils_and_custom_codes():
    requests = []
    async def handler(tid, unit, pdu):
        requests.append((unit, pdu))
        fn = pdu[0]
        if fn == 3:
            response = b"\x03\x02\x00\x0c"
        elif fn == 4:
            response = b"\x04\x04" + struct.pack(">f", -1250)
        elif fn in (1, 2):
            response = bytes([fn, 1, 1])
        elif fn == 16:
            response = pdu[:5]
        else:
            response = pdu
        return tid, unit, response
    async def exercise(client):
        c = config(kind="switch", data_type="uint16", command_on="12", command_off="14", address=15, device_id=7)
        assert await client.read(c) is True
        await client.write(c, False)
        assert requests[-1] == (7, bytes.fromhex("10000f000102000e"))
        await client.write({**c, "write_function": "single"}, True)
        assert requests[-1][1] == bytes.fromhex("06000f000c")
        assert await client.read(config(register_type="input", scale=.001)) == -1.25
        for area in ("coil", "discrete"):
            assert await client.read(config(register_type=area, data_type="uint16")) == 1
        await client.write(config(kind="switch", register_type="coil"), True)
        assert requests[-1][1] == bytes.fromhex("050000ff00")
        await client.write(config(kind="number", scale=.1), 12.5)
        assert requests[-1][1][6:] == struct.pack(">f", 125)
    asyncio.run(with_server(handler, exercise))


@pytest.mark.parametrize("failure", ["transaction", "unit", "function", "exception", "byte_count", "write_echo", "disconnect", "timeout"])
def test_tcp_rejects_bad_responses_and_does_not_replay_writes(failure):
    calls = []
    async def handler(tid, unit, pdu):
        calls.append(pdu)
        if failure == "disconnect":
            return None
        if failure == "timeout":
            await asyncio.sleep(1)
        if failure == "transaction":
            tid += 1
        if failure == "unit":
            unit += 1
        response = pdu if pdu[0] == 6 else b"\x03\x02\x00\x01"
        if failure == "function":
            response = b"\x04\x02\x00\x01"
        if failure == "exception":
            response = bytes([pdu[0] | 128, 2])
        if failure == "byte_count":
            response = b"\x03\x04\x00\x01"
        if failure == "write_echo":
            response = bytes.fromhex("0600010001")
        return tid, unit, response
    async def exercise(client):
        c = config(kind="number", data_type="uint16", write_function="single", timeout=.1)
        with pytest.raises(ModbusError):
            if failure == "byte_count":
                await client.read(c)
            else:
                await client.write(c, 12)
        assert len(calls) == 1
        assert client._writer is None
    asyncio.run(with_server(handler, exercise))


@pytest.fixture
def io_module(monkeypatch):
    for name, attributes in {
        "homeassistant": {}, "homeassistant.core": {"callback": lambda fn: fn},
        "homeassistant.components": {}, "homeassistant.exceptions": {"HomeAssistantError": type("HomeAssistantError", (RuntimeError,), {})},
    }.items():
        module = ModuleType(name)
        vars(module).update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    module_name = "custom_components.power_manager.direct_io"
    monkeypatch.delitem(sys.modules, module_name, raising=False)
    return importlib.import_module(module_name)


def test_mqtt_commands_retained_measurements_disconnect_expiry_and_cleanup(io_module, monkeypatch):
    io = io_module
    callbacks, messages, unsubscribed = {}, [], []
    connected = [True]
    mqtt = ModuleType("homeassistant.components.mqtt")
    async def subscribe(hass, topic, callback, qos=0):
        callbacks[topic] = callback
        return lambda: unsubscribed.append(topic)
    async def publish(hass, topic, payload, **kwargs):
        messages.append((topic, payload, kwargs))
    mqtt.async_subscribe, mqtt.async_publish = subscribe, publish
    mqtt.is_connected = lambda hass: connected[0]
    mqtt.async_subscribe_connection_status = lambda hass, cb: (callbacks.update(connection=cb) or (lambda: unsubscribed.append("connection")))
    monkeypatch.setitem(sys.modules, mqtt.__name__, mqtt)
    subentries = {key: SimpleNamespace(subentry_type="point", data=config(protocol="mqtt", **values)) for key, values in {
        "meter": {"state_topic": "meter", "scale": .001},
        "setpoint": {"kind": "number", "command_topic": "power/set", "scale": .1, "payload_template": '{"value":{value}}'},
        "enable": {"kind": "switch", "command_topic": "enable/set", "command_on": "12", "command_off": "14"},
        "readback": {"kind": "number", "state_topic": "actual", "command_topic": "actual/set"},
    }.items()}
    async def exercise():
        hass = SimpleNamespace(async_create_background_task=lambda coro, name: asyncio.create_task(coro))
        manager = io.DirectIO(hass, SimpleNamespace(entry_id="entry", subentries=subentries))
        manager.start()
        await asyncio.sleep(.01)
        assert not messages  # Setup and polling never publish commands.
        assert not manager.points["meter"].available
        assert manager.points["setpoint"].available and manager.points["setpoint"].value is None
        callbacks["meter"](SimpleNamespace(payload="5000", retain=True))
        assert not manager.points["meter"].available
        callbacks["meter"](SimpleNamespace(payload="5000", retain=False))
        assert manager.points["meter"].value == 5
        original_age = manager.points["meter"].updated
        await manager.write("setpoint", 12.5)
        assert messages[-1] == ("power/set", '{"value":125}', {"qos": 0, "retain": False})
        await manager.write("enable", True)
        await manager.write("enable", False)
        assert [msg[1] for msg in messages[-2:]] == ["12", "14"]
        await manager.write("readback", 100)
        assert manager.points["readback"].value is None
        assert manager.points["readback"].updated is None
        assert manager.points["meter"].updated == original_age
        callbacks["actual"](SimpleNamespace(payload="90", retain=False))
        assert manager.points["readback"].value == 90
        with pytest.raises(RuntimeError):
            await manager.write("setpoint", -1)
        connected[0] = False
        callbacks["connection"](False)
        assert not any(p.available for p in manager.points.values())
        with pytest.raises(RuntimeError):
            await manager.write("enable", True)
        connected[0] = True
        callbacks["connection"](True)
        assert manager.points["setpoint"].available
        assert manager.points["setpoint"].value is None  # Never deduplicate against a command from an earlier connection.
        assert not manager.points["meter"].available
        callbacks["meter"](SimpleNamespace(payload="5000", retain=False))
        # Equal repeated physical messages refresh age; commands cannot do so.
        assert manager.points["meter"].updated > original_age
        manager.points["meter"].updated -= 100
        await asyncio.sleep(1.01)
        assert not manager.points["meter"].available
        await manager.stop()
        assert sorted(unsubscribed) == ["actual", "connection", "meter"]
        assert all(task.done() for task in manager.tasks)
    asyncio.run(exercise())


def test_modbus_manager_polls_without_startup_writes_and_forgets_old_assumptions(io_module):
    writes = []
    mode = [14]
    async def handler(tid, unit, pdu):
        if pdu[0] == 4:
            response = b"\x04\x04" + struct.pack(">f", -2500)
        elif pdu[0] == 3:
            response = b"\x03\x02" + struct.pack(">H", mode[0])
        else:
            writes.append(pdu)
            if pdu[0] == 6:
                mode[0] = struct.unpack(">H", pdu[3:])[0]
                response = pdu
            else:
                response = pdu[:5]
        return tid, unit, response
    async def exercise(client):
        common = dict(port=client.port, poll_interval=1, timeout=.1, state_timeout=3)
        points = {
            "meter": config(**common, register_type="input", scale=.001),
            "power": config(**common, kind="number", readback=False, address=10),
            "enable": config(**common, kind="switch", data_type="uint16", write_function="single", address=20, command_on="12", command_off="14"),
        }
        entry = SimpleNamespace(entry_id="entry", subentries={key:SimpleNamespace(subentry_type="point", data=data) for key,data in points.items()})
        hass = SimpleNamespace(async_create_background_task=lambda coro,name:asyncio.create_task(coro))
        manager = io_module.DirectIO(hass, entry)
        event = asyncio.Event()
        for point in manager.points.values():
            point.listeners.add(event.set)
        manager.start()
        async with asyncio.timeout(2):
            while not all(point.available for point in manager.points.values()):
                event.clear()
                await event.wait()
        assert not writes
        assert manager.points["meter"].value == -2.5
        assert manager.points["enable"].value is False
        await manager.write("power", 2500)
        await manager.write("enable", True)
        assert len(writes) == 2
        assert manager.points["power"].value == 2500
        assert manager.points["enable"].value is False  # No synthetic readback.
        async with asyncio.timeout(2):
            while manager.points["enable"].value is not True:
                event.clear()
                await event.wait()
        await manager.client(points["power"]).close()
        async with asyncio.timeout(2):
            while manager.points["power"].value is not None:
                event.clear()
                await event.wait()
        assert len(writes) == 2  # Reconnect performs reads only.
        await manager.stop()
        assert all(task.done() for task in manager.tasks)
    asyncio.run(with_server(handler, exercise))
