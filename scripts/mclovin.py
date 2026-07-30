"""McLovin — BLE control library for Mictuning N8H-1AF LED controllers.

Uses the Dream Light protocol (A0/A1/A2/A3/AD commands) over BLE GATT.
See PROTOCOL.md for packet format details.
"""

import asyncio
import logging

from bleak import BleakClient, BleakScanner

log = logging.getLogger(__name__)

# BLE UUIDs
SERVICE_UUID = "0003cbbb-0000-1000-8000-00805f9bfff0"
CHAR_FFF1 = "0003cbbb-0000-1000-8000-00805f9bfff1"
CHAR_FFFA = "0003cbbb-0000-1000-8000-00805f9bfffa"

DEVICE_NAME = "N8H-1AF"

# Animation modes (Dream Light protocol)
MODE_RUNNING_CYCLE = 0x01
MODE_TAILING = 0x04
MODE_WATERING = 0x05
MODE_OPENING_CLOSING = 0x06
MODE_CHASING = 0x07
MODE_WAVING = 0x08
MODE_RUNNING_RAINBOW = 0x0C
MODE_STATIC = 0x0D

MODE_NAMES = {
    MODE_RUNNING_CYCLE: "Running Cycle",
    MODE_TAILING: "Tailing",
    MODE_WATERING: "Watering",
    MODE_OPENING_CLOSING: "Opening & Closing",
    MODE_CHASING: "Chasing",
    MODE_WAVING: "Waving",
    MODE_RUNNING_RAINBOW: "Running Rainbow",
    MODE_STATIC: "Static",
}


class McLovin:
    """Control a Mictuning LED controller over BLE."""

    def __init__(self):
        self._client: BleakClient | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @staticmethod
    async def scan(timeout: float = 10.0, name_filter: str | None = DEVICE_NAME) -> list:
        """Scan for BLE devices advertising the controller service.

        Returns a list of BLEDevice objects. If name_filter is set,
        only devices whose name contains the filter string are returned.
        Pass name_filter=None to return all devices with the matching
        service UUID.
        """
        log.info("Scanning for BLE devices (timeout=%.1fs)...", timeout)
        devices = await BleakScanner.discover(
            timeout=timeout,
            service_uuids=[SERVICE_UUID],
        )
        if name_filter is not None:
            devices = [d for d in devices if d.name and name_filter in d.name]
        log.info("Found %d device(s)", len(devices))
        return devices

    async def connect(self, address: str, timeout: float = 10.0):
        """Connect to the controller at the given MAC address."""
        self._client = BleakClient(address)
        await self._client.connect(timeout=timeout)
        log.info("Connected to %s", address)

    async def disconnect(self):
        """Disconnect from the controller."""
        if self._client is not None:
            await self._client.disconnect()
            log.info("Disconnected")
            self._client = None

    # --- High-level commands ---

    async def on(self, brightness: int = 255, speed: int = 1, save: bool = True):
        """Turn the lights on."""
        if not 1 <= brightness <= 255:
            raise ValueError(f"brightness must be 1-255, got {brightness}")
        if not 1 <= speed <= 100:
            raise ValueError(f"speed must be 1-100, got {speed}")
        pkt = self._build_a0(on_off=1, speed=speed, brightness=brightness,
                             save=int(save))
        await self.send_raw(pkt)

    async def off(self, save: bool = True):
        """Turn the lights off."""
        pkt = self._build_a0(on_off=0, speed=1, brightness=255, save=int(save))
        await self.send_raw(pkt)

    async def set_brightness(self, value: int, save: bool = False):
        """Set brightness (2-255). Use save=False for live slider updates.

        Sends on_off=1, which will turn the light on if it is currently off.
        """
        if not 1 <= value <= 255:
            raise ValueError(f"brightness must be 1-255, got {value}")
        pkt = self._build_a0(on_off=1, speed=1, brightness=value, save=int(save))
        await self.send_raw(pkt)

    async def set_speed(self, value: int, save: bool = False):
        """Set animation speed (1-100). Use save=False for live slider updates.

        Sends on_off=1, which will turn the light on if it is currently off.
        """
        if not 1 <= value <= 100:
            raise ValueError(f"speed must be 1-100, got {value}")
        pkt = self._build_a0(on_off=1, speed=value, brightness=255, save=int(save))
        await self.send_raw(pkt)

    async def set_colors(self, colors: list[tuple[int, int, int]]):
        """Set colors (1-14 RGB tuples) via A2, optionally A3 and A4.

        Does NOT send A1 — call set_mode() after this to activate.
        """
        if not 1 <= len(colors) <= 14:
            raise ValueError(f"Expected 1-14 colors, got {len(colors)}")
        pkt_a2 = self._build_a2(colors[:6])
        await self.send_raw(pkt_a2)
        if len(colors) > 6:
            pkt_a3 = self._build_a3(colors[6:12])
            await self.send_raw(pkt_a3)
        if len(colors) > 12:
            pkt_a4 = self._build_a4(colors[12:14])
            await self.send_raw(pkt_a4)

    async def set_mode(self, mode: int, direction: int = 0, speed: int = 1,
                       color_count: int = 1, brightness: int = 255,
                       bg_color: tuple[int, int, int] = (0, 0, 0)):
        """Set animation mode via A1 command.

        For static mode (0x0D), direction is set to 0x02 and mode_speed to 0x64
        automatically.
        """
        if mode == MODE_STATIC:
            direction = 0x02
            mode_speed = 0x64
        else:
            mode_speed = 0x00
        pkt = self._build_a1(
            mode=mode, direction=direction, on_off=1, speed=speed,
            brightness=brightness, mode_speed=mode_speed,
            color_count=color_count,
            bg_r=bg_color[0], bg_g=bg_color[1], bg_b=bg_color[2],
        )
        await self.send_raw(pkt)

    async def set_streamer_length(self, length: int):
        """Set the streamer (LED strip) length."""
        pkt = self._build_ad(length)
        await self.send_raw(pkt)

    async def get_streamer_length(self) -> int:
        """Query the current streamer length.

        Subscribes to notifications on FFF1, sends AD 00, and waits for
        the response.
        """
        result: asyncio.Future[int] = asyncio.get_running_loop().create_future()

        def on_notify(_sender, data: bytearray):
            if len(data) >= 2 and data[0] == 0xAD:
                if not result.done():
                    result.set_result(data[1])

        await self._client.start_notify(CHAR_FFF1, on_notify)
        try:
            await self.send_raw(self._build_ad(0))
            length = await asyncio.wait_for(result, timeout=5.0)
            return length
        finally:
            await self._client.stop_notify(CHAR_FFF1)

    # --- Low-level ---

    async def send_raw(self, data: bytes):
        """Write raw bytes to the FFF1 characteristic (write without response)."""
        if not self.connected:
            raise RuntimeError("Not connected")
        log.debug("TX: %s", data.hex())
        await self._client.write_gatt_char(CHAR_FFF1, data, response=False)

    @staticmethod
    def _checksum(data: bytes) -> int:
        """Compute checksum: sum of all bytes, masked to 8 bits."""
        return sum(data) & 0xFF

    def _build_a0(self, on_off: int, speed: int, brightness: int,
                  strobe: int = 0, save: int = 1) -> bytes:
        """Build an A0 (on/off + speed + brightness) packet.

        Total: 8 bytes including checksum.
        """
        body = bytes([
            0xA0,
            on_off & 0xFF,
            (speed >> 8) & 0xFF,  # speed high byte
            speed & 0xFF,         # speed low byte
            brightness & 0xFF,
            strobe & 0xFF,
            save & 0xFF,
        ])
        return body + bytes([self._checksum(body)])

    def _build_a1(self, mode: int, direction: int, on_off: int, speed: int,
                  brightness: int, mode_speed: int, color_count: int,
                  bg_r: int, bg_g: int, bg_b: int) -> bytes:
        """Build an A1 (mode + control) packet.

        Total: 13 bytes including checksum.
        """
        body = bytes([
            0xA1,
            mode & 0xFF,
            direction & 0xFF,
            on_off & 0xFF,
            (speed >> 8) & 0xFF,
            speed & 0xFF,
            brightness & 0xFF,
            mode_speed & 0xFF,
            color_count & 0xFF,
            bg_r & 0xFF,
            bg_g & 0xFF,
            bg_b & 0xFF,
        ])
        return body + bytes([self._checksum(body)])

    def _build_a2(self, colors: list[tuple[int, int, int]]) -> bytes:
        """Build an A2 (color slots 0-5) packet.

        Always 20 bytes: 1 cmd + 18 color bytes + 1 checksum.
        Unused slots are zero-padded.
        """
        body = bytearray([0xA2])
        for i in range(6):
            if i < len(colors):
                r, g, b = colors[i]
                body.extend([r & 0xFF, g & 0xFF, b & 0xFF])
            else:
                body.extend([0x00, 0x00, 0x00])
        return bytes(body) + bytes([self._checksum(body)])

    def _build_a3(self, colors: list[tuple[int, int, int]]) -> bytes:
        """Build an A3 (color slots 6-11) packet.

        Same structure as A2 but for overflow colors.
        """
        body = bytearray([0xA3])
        for i in range(6):
            if i < len(colors):
                r, g, b = colors[i]
                body.extend([r & 0xFF, g & 0xFF, b & 0xFF])
            else:
                body.extend([0x00, 0x00, 0x00])
        return bytes(body) + bytes([self._checksum(body)])

    def _build_a4(self, colors: list[tuple[int, int, int]]) -> bytes:
        """Build an A4 (color slots 12-13) packet.

        Fixed 8 bytes, not zero-padded to 20 like A2/A3.
        """
        body = bytearray([0xA4])
        for i in range(2):
            if i < len(colors):
                r, g, b = colors[i]
                body.extend([r & 0xFF, g & 0xFF, b & 0xFF])
            else:
                body.extend([0x00, 0x00, 0x00])
        return bytes(body) + bytes([self._checksum(body)])

    def _build_ad(self, length: int) -> bytes:
        """Build an AD (streamer length) packet.

        length=0 means query, non-zero means set.
        Total: 3 bytes.
        """
        body = bytes([0xAD, length & 0xFF])
        return body + bytes([self._checksum(body)])
