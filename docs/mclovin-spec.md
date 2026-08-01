# McLovin Library Spec

Source of truth for the `McLovin` class API in `src/mclovin/lib.py`.

## Overview

McLovin is an async Python library for controlling Mictuning LED controllers
over BLE GATT. It uses the Dream Light protocol (command bytes
A0/A1/A2/A3/AD) and communicates via bleak.

Dependency: [bleak](https://github.com/hbldh/bleak)

## Constants

### BLE identifiers

| Name           | Value                                    | Description                  |
|----------------|------------------------------------------|------------------------------|
| `SERVICE_UUID` | `0003cbbb-0000-1000-8000-00805f9bfff0`   | GATT service UUID            |
| `CHAR_FFF1`    | `0003cbbb-0000-1000-8000-00805f9bfff1`   | Read/write characteristic    |
| `CHAR_FFFA`    | `0003cbbb-0000-1000-8000-00805f9bfffa`   | Secondary characteristic     |

### Animation modes

| Constant                 | Value  | Display name        |
|--------------------------|--------|---------------------|
| `MODE_RUNNING_CYCLE`     | `0x01` | Running Cycle       |
| `MODE_TAILING`           | `0x04` | Tailing             |
| `MODE_WATERING`          | `0x05` | Watering            |
| `MODE_OPENING_CLOSING`   | `0x06` | Opening & Closing   |
| `MODE_CHASING`           | `0x07` | Chasing             |
| `MODE_WAVING`            | `0x08` | Waving              |
| `MODE_RUNNING_RAINBOW`   | `0x0C` | Running Rainbow     |
| `MODE_STATIC`            | `0x0D` | Static              |

`MODE_NAMES` is a dict mapping each mode constant to its display name.

## Class: McLovin

### Constructor

```python
McLovin()
```

No arguments. Creates an unconnected controller handle. Internal state:
- `_client: BleakClient | None` — set by `connect()`, cleared by `disconnect()`.

### Properties

#### `connected -> bool`

`True` if `_client` is not `None` and `_client.is_connected`.

---

### Connection methods

#### `scan(timeout, name_filter) -> list` (static, async)

```python
@staticmethod
async def scan(timeout: float = 10.0, name_filter: str | None = None) -> list
```

Discover BLE devices advertising `SERVICE_UUID`.

| Parameter     | Type             | Default       | Description                                      |
|---------------|------------------|---------------|--------------------------------------------------|
| `timeout`     | `float`          | `10.0`        | Scan duration in seconds                         |
| `name_filter` | `str \| None`    | `None`        | Substring match on device name; `None` to skip   |

**Returns:** list of `BLEDevice` objects (from bleak). May be empty.

**Behavior:** Calls `BleakScanner.discover()` filtered to `SERVICE_UUID`. If
`name_filter` is not `None`, further filters to devices whose name contains the
filter string.

#### `connect(address, timeout)` (async)

```python
async def connect(self, address: str, timeout: float = 10.0)
```

Connect to a controller by MAC address.

| Parameter | Type    | Default | Description                  |
|-----------|---------|---------|------------------------------|
| `address` | `str`   | —       | MAC address (required)       |
| `timeout` | `float` | `10.0`  | Connection timeout, seconds  |

**Side effects:** Sets `self._client`.

**Raises:** `BleakError` on connection failure.

#### `disconnect()` (async)

```python
async def disconnect(self)
```

Disconnect and clear `self._client`. Safe to call when already disconnected.

---

### High-level commands

All high-level commands require an active connection (`self.connected` must be
`True`) or `send_raw` will raise `RuntimeError`.

#### `on(brightness, speed, save)` (async)

```python
async def on(self, brightness: int = 255, speed: int = 1, save: bool = True)
```

Turn the lights on. Sends an A0 packet with `on_off=1`.

| Parameter    | Type   | Default | Range   | Description                       |
|--------------|--------|---------|---------|-----------------------------------|
| `brightness` | `int`  | `255`   | 1-255   | Initial brightness level          |
| `speed`      | `int`  | `1`     | 1-100   | Animation speed                   |
| `save`       | `bool` | `True`  |         | Persist state to controller flash |

**Raises:** `ValueError` if brightness or speed out of range.

#### `off(save)` (async)

```python
async def off(self, save: bool = True)
```

Turn the lights off. Sends A0 with `on_off=0`, `speed=1`, `brightness=255`.

| Parameter | Type   | Default | Description                       |
|-----------|--------|---------|-----------------------------------|
| `save`    | `bool` | `True`  | Persist state to controller flash |

#### `set_brightness(value, save)` (async)

```python
async def set_brightness(self, value: int, save: bool = False)
```

Set brightness. Sends A0 with `on_off=1` (implicit turn-on), `speed=1`.

| Parameter | Type   | Default | Range | Description                               |
|-----------|--------|---------|-------|-------------------------------------------|
| `value`   | `int`  | —       | 2-255 | Brightness level                          |
| `save`    | `bool` | `False` |       | `False` for live slider, `True` to persist |

**Side effect:** Turns the light on if currently off (`on_off=1`).

**Raises:** `ValueError` if value out of range.

#### `set_speed(value, save)` (async)

```python
async def set_speed(self, value: int, save: bool = False)
```

Set animation speed. Sends A0 with `on_off=1` (implicit turn-on),
`brightness=255`.

| Parameter | Type   | Default | Range | Description                               |
|-----------|--------|---------|-------|-------------------------------------------|
| `value`   | `int`  | —       | 1-100 | Speed level                               |
| `save`    | `bool` | `False` |       | `False` for live slider, `True` to persist |

**Side effect:** Turns the light on if currently off (`on_off=1`).

**Raises:** `ValueError` if value out of range.

#### `set_colors(colors)` (async)

```python
async def set_colors(self, colors: list[tuple[int, int, int]])
```

Set color palette via A2 (and A3 if >6 colors). Does **not** activate the
colors — call `set_mode()` afterward.

| Parameter | Type                         | Range      | Description          |
|-----------|------------------------------|------------|----------------------|
| `colors`  | `list[tuple[int, int, int]]` | 1-12 items | RGB tuples (0-255)   |

**Raises:** `ValueError` if color count out of range.

**Protocol detail:** Sends one A2 packet (slots 0-5). If more than 6 colors,
also sends an A3 packet (slots 6-11). Unused slots are zero-padded.

#### `set_mode(mode, direction, speed, color_count, brightness, bg_color)` (async)

```python
async def set_mode(self, mode: int, direction: int = 0, speed: int = 1,
                   color_count: int = 1, brightness: int = 255,
                   bg_color: tuple[int, int, int] = (0, 0, 0))
```

Set animation mode via A1 packet. Always sends `on_off=1`.

| Parameter     | Type                    | Default      | Description                          |
|---------------|-------------------------|--------------|--------------------------------------|
| `mode`        | `int`                   | —            | One of the `MODE_*` constants        |
| `direction`   | `int`                   | `0`          | Animation direction (overridden for static) |
| `speed`       | `int`                   | `1`          | Animation speed                      |
| `color_count` | `int`                   | `1`          | Number of active colors from palette |
| `brightness`  | `int`                   | `255`        | Brightness level                     |
| `bg_color`    | `tuple[int, int, int]`  | `(0, 0, 0)`  | Background RGB color                 |

**Static mode override:** When `mode == MODE_STATIC`, `direction` is forced to
`0x02` and `mode_speed` is set to `0x64` regardless of arguments.

#### `set_streamer_length(length)` (async)

```python
async def set_streamer_length(self, length: int)
```

Set the LED strip length. Sends an AD packet.

#### `get_streamer_length() -> int` (async)

```python
async def get_streamer_length(self) -> int
```

Query the current strip length. Subscribes to notifications on `CHAR_FFF1`,
sends `AD 00`, and waits up to 5 seconds for the response byte.

**Returns:** Length as int.

**Raises:** `asyncio.TimeoutError` after 5 seconds with no response.

---

### Low-level methods

#### `send_raw(data)` (async)

```python
async def send_raw(self, data: bytes)
```

Write raw bytes to `CHAR_FFF1` (write-without-response).

**Raises:** `RuntimeError` if not connected.

#### `_checksum(data) -> int` (static)

```python
@staticmethod
def _checksum(data: bytes) -> int
```

Sum of all bytes, masked to 8 bits (`& 0xFF`).

#### `_build_a0(on_off, speed, brightness, strobe, save) -> bytes`

Build an A0 power/brightness/speed packet. 8 bytes (7 body + 1 checksum).

| Byte | Field           | Notes                   |
|------|-----------------|-------------------------|
| 0    | `0xA0`          | Command                 |
| 1    | `on_off`        | 0=off, 1=on             |
| 2    | speed high byte |                         |
| 3    | speed low byte  |                         |
| 4    | brightness      |                         |
| 5    | strobe          | Default 0               |
| 6    | save            | 1=persist, 0=transient  |
| 7    | checksum        |                         |

#### `_build_a1(mode, direction, on_off, speed, brightness, mode_speed, color_count, bg_r, bg_g, bg_b) -> bytes`

Build an A1 mode packet. 13 bytes (12 body + 1 checksum).

| Byte | Field       |
|------|-------------|
| 0    | `0xA1`      |
| 1    | mode        |
| 2    | direction   |
| 3    | on_off      |
| 4    | speed high  |
| 5    | speed low   |
| 6    | brightness  |
| 7    | mode_speed  |
| 8    | color_count |
| 9    | bg_r        |
| 10   | bg_g        |
| 11   | bg_b        |
| 12   | checksum    |

#### `_build_a2(colors) -> bytes`

Build an A2 color-slots-0-5 packet. Always 20 bytes (1 cmd + 18 color + 1
checksum). Unused slots zero-padded.

#### `_build_a3(colors) -> bytes`

Build an A3 color-slots-6-11 packet. Same structure as A2.

#### `_build_ad(length) -> bytes`

Build an AD streamer-length packet. 3 bytes (1 cmd + 1 length + 1 checksum).
`length=0` means query; non-zero means set.

---

## Typical usage

```python
from mclovin import McLovin, MODE_STATIC, MODE_CHASING

m = McLovin()

# Discover controllers
devices = await McLovin.scan()
await m.connect(devices[0].address)

# Solid red
await m.set_colors([(255, 0, 0)])
await m.set_mode(MODE_STATIC, color_count=1)

# Chasing animation with three colors
await m.set_colors([(255, 0, 0), (0, 255, 0), (0, 0, 255)])
await m.set_mode(MODE_CHASING, color_count=3, speed=50)

# Adjust brightness (also turns on if off)
await m.set_brightness(128)

# Turn off
await m.off()
await m.disconnect()
```

## Validation summary

High-level methods validate inputs and raise `ValueError`:

| Method           | Parameter    | Valid range |
|------------------|-------------|-------------|
| `on`             | brightness  | 1-255       |
| `on`             | speed       | 1-100       |
| `set_brightness` | value       | 2-255       |
| `set_speed`      | value       | 1-100       |
| `set_colors`     | len(colors) | 1-12        |

Low-level `_build_*` methods do **not** validate — they mask values to 8 bits
and are the escape hatch for experimentation.
