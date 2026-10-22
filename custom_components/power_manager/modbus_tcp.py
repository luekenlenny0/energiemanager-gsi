"""Small asynchronous Modbus TCP client; no automatic replay of writes."""

import asyncio
from math import isfinite
import struct

from .point_config import DATA_TYPES


class ModbusError(RuntimeError):
    """A request was rejected or its response could not be verified."""


def _swap(data, config):
    words = [data[index:index + 2] for index in range(0, len(data), 2)]
    if config["byte_order"] == "little":
        words = [word[::-1] for word in words]
    if config["word_order"] == "little":
        words.reverse()
    return b"".join(words)


def register_count(config):
    return struct.calcsize(DATA_TYPES[config["data_type"]]) // 2


def decode_registers(data, config):
    result = struct.unpack(">" + DATA_TYPES[config["data_type"]], _swap(data, config))[0] * config["scale"]
    if not isfinite(result):
        raise ModbusError("Non-finite Modbus measurement")
    return result


def encode_registers(value, config):
    raw = float(value) / config["scale"]
    if not isfinite(raw):
        raise ValueError("Non-finite setpoint")
    code = DATA_TYPES[config["data_type"]]
    if code in ("H", "h", "I", "i"):
        nearest = round(raw)
        if abs(raw - nearest) > 1e-7:
            raise ValueError("Setpoint cannot be represented by this integer register and scale")
        raw = nearest
    try:
        data = struct.pack(">" + code, raw)
    except (struct.error, OverflowError) as err:
        raise ValueError("Setpoint outside register range") from err
    if code in ("f", "d") and not isfinite(struct.unpack(">" + code, data)[0]):
        raise ValueError("Setpoint outside register range")
    return _swap(data, config)


class ModbusTCPClient:
    """Serialize requests per TCP endpoint and validate the complete response."""

    def __init__(self, host, port):
        self.host, self.port = host, port
        self._reader = self._writer = None
        self._lock = asyncio.Lock()
        self._transaction = 0
        self.generation = 0

    async def close(self):
        writer = self._writer
        self._reader = self._writer = None
        if writer:
            writer.close()
            try:
                async with asyncio.timeout(1):
                    await writer.wait_closed()
            except (OSError, TimeoutError):
                pass

    async def connect(self, timeout):
        """Probe a write-only endpoint without sending any device command."""
        async with self._lock:
            try:
                async with asyncio.timeout(timeout):
                    if self._writer is None or self._writer.is_closing() or self._reader.at_eof():
                        await self.close()
                        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
                        self.generation += 1
            except (OSError, TimeoutError) as err:
                await self.close()
                raise ModbusError(str(err) or "Modbus connection timeout") from err

    async def request(self, unit, pdu, timeout):
        async with self._lock:
            try:
                async with asyncio.timeout(timeout):
                    if self._writer is None or self._writer.is_closing():
                        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
                        self.generation += 1
                    self._transaction = (self._transaction + 1) & 0xFFFF
                    self._writer.write(struct.pack(">HHHB", self._transaction, 0, len(pdu) + 1, unit) + pdu)
                    await self._writer.drain()
                    transaction, protocol, length, response_unit = struct.unpack(">HHHB", await self._reader.readexactly(7))
                    if transaction != self._transaction or protocol != 0 or response_unit != unit or not 2 <= length <= 254:
                        raise ModbusError("Invalid MBAP response header")
                    response = await self._reader.readexactly(length - 1)
                    if response[0] == (pdu[0] | 0x80):
                        if len(response) != 2:
                            raise ModbusError("Malformed exception response")
                        raise ModbusError(f"Modbus exception {response[1]} (function {pdu[0]})")
                    if response[0] != pdu[0]:
                        raise ModbusError("Unexpected Modbus function")
                    return response
            except asyncio.CancelledError:
                await self.close()
                raise
            except (OSError, EOFError, asyncio.IncompleteReadError, TimeoutError, ModbusError) as err:
                await self.close()
                raise ModbusError(str(err) or "Modbus timeout/disconnect") from err

    async def read(self, config):
        function = {"holding": 3, "input": 4, "coil": 1, "discrete": 2}[config["register_type"]]
        bits = function in (1, 2)
        count = 1 if bits else register_count(config)
        result = await self.request(config["device_id"], struct.pack(">BHH", function, config["address"], count), config["timeout"])
        expected = 1 if bits else count * 2
        if len(result) != expected + 2 or result[1] != expected:
            await self.close()
            raise ModbusError("Invalid Modbus byte count")
        value = (result[2] & 1) if bits else decode_registers(result[2:], config)
        if config["kind"] == "switch":
            if bits:
                return bool(value)
            if result[2:] == encode_registers(float(config["command_on"]), config):
                return True
            if result[2:] == encode_registers(float(config["command_off"]), config):
                return False
            raise ModbusError("Register contains neither ON nor OFF value")
        return value

    async def write(self, config, value):
        address = config["address"]
        if config["register_type"] == "coil":
            pdu = struct.pack(">BHH", 5, address, 0xFF00 if value else 0)
            expected = pdu
        else:
            native = float(config["command_on"] if value else config["command_off"]) if config["kind"] == "switch" else float(value)
            data = encode_registers(native, config)
            if config["write_function"] == "single":
                if len(data) != 2:
                    raise ValueError("FC6 requires one register")
                pdu = struct.pack(">BH", 6, address) + data
                expected = pdu
            else:
                count = len(data) // 2
                pdu = struct.pack(">BHHB", 16, address, count, len(data)) + data
                expected = struct.pack(">BHH", 16, address, count)
        response = await self.request(config["device_id"], pdu, config["timeout"])
        if response != expected:
            await self.close()
            raise ModbusError("Write response does not acknowledge this address/value")
