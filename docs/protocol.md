# Mictuning N8H-1AF Bluetooth Protocol Spec

Status: **Draft** — validated against HCI snoop capture + decompiled APK source.
Gaps marked with `[?]`.

## Discovery

The app scans for both BLE and Classic Bluetooth devices with **no service UUID
filter**. It matches discovered devices by **advertised name** against a product
database fetched from a server and cached locally.

Name matching (`ProductUtil.findProduct()`):
- Exact match: `name == bleMatchName`
- With suffix: `name == bleMatchName + "S"` or `name == bleMatchName + "_S"`

Each product entry has a `lightType` field (`deviceType` in JSON) that determines
which protocol variant to use:
- `lightType == 1` → RGB / "Ship & Car" protocol (B2/C2 commands)
- `lightType == 2 or 3` → "Dream light" protocol (A2/A3 commands)

Transport is auto-detected from `BluetoothDevice.getType()`:
- `1` = Classic → SPP
- `2` = BLE

To discover a controller without the app, scan for BLE devices and look for the
service UUID below, or match by name.

## Transport

- **Bluetooth Low Energy** (not SPP, despite APK package name `headlightSpp`)
- **Write type**: Write Without Response (ATT opcode `0x52`)
- **No framing**: packets are written directly as characteristic values

### BLE UUIDs

| Role | UUID |
|------|------|
| Service | `0003CBBB-0000-1000-8000-00805F9BFFF0` |
| Write characteristic (FFF1) | `0003CBBB-0000-1000-8000-00805F9BFFF1` |
| FFF2 | `0003CBBB-0000-1000-8000-00805F9BFFF2` |
| FFF3 | `0003CBBB-0000-1000-8000-00805F9BFFF3` |
| FFF4 | `0003CBBB-0000-1000-8000-00805F9BFFF4` |
| FFF5 | `0003CBBB-0000-1000-8000-00805F9BFFF5` |
| FFFA (notify/cmd) | `0003CBBB-0000-1000-8000-00805F9BFFFA` |

Commands are written to **FFF1**. The app subscribes to notifications on **FFF1**
(for Dream light types) or **FFFA** (for P2D commands). FFF2-FFF4 are used for
multi-part color data in the RGB protocol path. FFF5 is used for F5 data
(non-Dream types).

There is also a secondary UUID set in the source (possibly for older hardware):
- Service: `0000FFF0-0000-1000-8000-00805F9B34FB`
- Characteristic: `0000FFF1-0000-1000-8000-00805F9B34FB`

ATT handle `0x0018` on N8H-1AF maps to the FFF1 write characteristic.

### SPP (Classic Bluetooth)

The app also supports SPP for other product variants. Same packet format,
written as raw bytes to the SPP serial socket.

## Packet Format

All commands share the same structure:

	[command_id] [payload...] [checksum]

- **Command ID**: 1 byte
- **Payload**: variable length, command-dependent
- **Checksum**: 1 byte = `sum(all preceding bytes) & 0xFF`

All multi-byte integers are **big-endian**.

## Commands

### A0 — On/Off + Speed + Brightness

Controls power state, animation speed, and brightness. Sent independently (not
part of a color/mode burst). Also used for live slider updates.

	A0 [on_off] [speed_hi] [speed_lo] [brightness] [unknown] [save] [checksum]

| Offset | Field | Size | Range | Notes |
|--------|-------|------|-------|-------|
| 0 | Command | 1 | `0xA0` | |
| 1 | On/Off | 1 | `0x00`=off, `0x01`=on | |
| 2-3 | Speed | 2 | 1-100, 16-bit BE | Animation speed. High byte always `0x00` |
| 4 | Brightness | 1 | 2-255 | `0xFF`=max, `0x02`=min observed |
| 5 | Strobe? | 1 | `[?]` | Usually `0x00`. `0x1E` (30) observed in state restore. Possibly strobe rate/mode — RCU has Strobe+/- buttons not in app UI `[?]` |
| 6 | Save | 1 | `0x00`/`0x01` | `0x00`=transient (slider dragging), `0x01`=persist (slider released) |
| 7 | Checksum | 1 | | |

**Total: 8 bytes**

Examples:
```
a0 01 0001 ff 00 01 a2    Turn on, speed=1, brightness=255, save
a0 00 0001 ff 00 01 a1    Turn off, speed=1, brightness=255, save
a0 01 0064 ff 00 01 05    Speed=100 (max), brightness=255, save
a0 01 0001 02 00 00 a4    Speed=1, brightness=2 (min), no save (dragging)
a0 01 0001 bd 1e 00 7d    Speed=1, brightness=189, byte5=0x1e [?]
```

> **Save flag**: during slider drags, `save=0` sends live updates without
> writing to flash. When the slider is released, `save=1` persists the final
> value. This reduces flash wear on the controller.

### A1 — Mode + Control

Sets the animation mode, direction, speed, and color count. Always sent after
A2 (and A3 if needed).

	A1 [mode] [direction] [on_off] [speed_hi] [speed_lo] [brightness] [mode_speed] [color_count] [bg_r] [bg_g] [bg_b] [checksum]

| Offset | Field          | Size | Range                                         | Notes                                                                         |
|--------|----------------|------|-----------------------------------------------|-------------------------------------------------------------------------------|
| 0      | Command        | 1    | `0xA1`                                        |                                                                               |
| 1      | Mode           | 1    | see mode table                                |                                                                               |
| 2      | Direction      | 1    | `0x00`=forward, `0x01`=backward, `0x02`=cycle  | `0x02` = alternating/both directions                                          |
| 3      | On/Off         | 1    | `0x00`/`0x01`                                 |                                                                               |
| 4-5    | Speed          | 2    | 1-100, 16-bit BE                              | Same speed as A0 bytes 2-3                                                    |
| 6      | Brightness     | 1    | 2-255                                         |                                                                               |
| 7      | Mode speed     | 1    | `[?]`                                         | `0x64` (100) in static mode, `0x00` in effects. Separate from A0 speed? `[?]` |
| 8      | Color count    | 1    | 1-14                                          | Number of active colors in A2 (+A3 +A4)                                       |
| 9-11   | Background RGB | 3    |                                               | Always `000000` in captures `[?]`                                             |
| 12     | Checksum       | 1    |                                               |                                                                               |

**Total: 13 bytes**

Examples:
```
a1 0d 02 01 0001 ff 64 01 000000 16    Static single color, speed=100
a1 05 00 01 0001 ff 00 03 000000 aa    Flow water, forward, 3 colors
a1 05 01 01 0001 ff 00 03 000000 ab    Flow water, backward, 3 colors
a1 07 00 01 0001 ff 00 03 000000 ac    Chasing, forward, 3 colors
a1 07 01 01 0001 ff 00 03 000000 ad    Chasing, backward, 3 colors
a1 08 00 01 0001 ff 00 07 000000 b1    Float, 7 colors
```

### A2 — Color List (slots 0-5)

Sets up to 6 RGB colors. Unused slots are zero-padded.

	A2 [R0 G0 B0] [R1 G1 B1] [R2 G2 B2] [R3 G3 B3] [R4 G4 B4] [R5 G5 B5] [checksum]

| Offset | Field | Size | Notes |
|--------|-------|------|-------|
| 0 | Command | 1 | `0xA2` |
| 1-3 | Color 0 | 3 | RGB, or `000000` if unused |
| 4-6 | Color 1 | 3 | |
| 7-9 | Color 2 | 3 | |
| 10-12 | Color 3 | 3 | |
| 13-15 | Color 4 | 3 | |
| 16-18 | Color 5 | 3 | |
| 19 | Checksum | 1 | |

**Total: 20 bytes (fixed)**

Examples:
```
a2 fd0000 000000 000000 000000 000000 000000 9f    Red only
a2 0001fb 000000 000000 000000 000000 000000 9e    Blue only
a2 00ff01 000000 000000 000000 000000 000000 a2    Green only
a2 ff0000 0000ff 00ff00 000000 000000 000000 9f    Red, blue, green
a2 ff0000 0000ff 00ff00 ffff00 00ffff ff00ff 9f    6 colors (R,B,G,Y,C,M)
```

### A3 — Color List (slots 6-11)

Overflow for colors 7-12. Same structure as A2. Only sent when color count > 6.

	A3 [R6 G6 B6] [R7 G7 B7] ... [R11 G11 B11] [checksum]

**Total: 20 bytes (fixed)**

Example:
```
a3 ffffff 000000 000000 000000 000000 000000 a0    Slot 6 = white
```

### A4 — Color List (slots 12-13)

Overflow for colors 13-14. Only sent when color count > 12. Unlike A2/A3,
A4 is **not** zero-padded to 20 bytes — it carries exactly 2 color slots.

	A4 [R12 G12 B12] [R13 G13 B13] [checksum]

| Offset | Field | Size | Notes |
|--------|-------|------|-------|
| 0 | Command | 1 | `0xA4` |
| 1-3 | Color 12 | 3 | RGB |
| 4-6 | Color 13 | 3 | RGB |
| 7 | Checksum | 1 | |

**Total: 8 bytes (fixed)**

The source code (`ControlUtil.sendDreamColor()`) has 6 slots in A4
(colors 12-17), but the app UI caps at 14 colors, so only 2 slots
are ever populated. Slots 14-17 are unused.

Examples:
```
a4 ffffff 000000 a1    Slot 12 = white, slot 13 = black
a4 ff00da 00fdff 79    Slot 12 = pink, slot 13 = cyan
```

### AD — Streamer Length Query/Set

Queries or sets the streamer (LED strip) length. Controls how many LEDs in the
strip are addressed by animations.

	AD [length] [checksum]

| Offset | Field | Size | Notes |
|--------|-------|------|-------|
| 0 | Command | 1 | `0xAD` |
| 1 | Length | 1 | `0x00` = query; non-zero = set length |
| 2 | Checksum | 1 | |

**Total: 3 bytes**

When queried (`AD 00`), the device responds via notification with the current
length in the same format.

Examples:
```
ad 00 ad              Query streamer length
ad 46 f3              Response/set: length=70 (0x46)
ad 78 25              Set length=120 (0x78)
```

Observed range: 70–120 (slider sweep). No save flag — takes effect immediately.
Live slider dragging sends one AD command per tick (~150ms apart).

### AE — Unknown

	AE [param] [checksum]

| Offset | Field | Size | Notes |
|--------|-------|------|-------|
| 0 | Command | 1 | `0xAE` |
| 1 | Param | 1 | `0x00` observed |
| 2 | Checksum | 1 | |

**Total: 3 bytes**

Sent after AD and before mode changes. Purpose unknown. `[?]`

## Mode Table

### Dream Light modes (N8H-1AF)

Source: `resources/assets/model.json` in the APK. The 76 UI presets are
combinations of 7 animation algorithms + direction + color presets.

| Hex | Animation | UI Presets | Capture |
|-----|-----------|------------|---------|
| `0x00` | Custom sequence | custom editor | confirmed |
| `0x01` | Running Cycle | 6 (modes 51–56) | not yet |
| `0x04` | Tailing | 20 (modes 31–50) | not yet |
| `0x05` | Watering (Flow water) | 10 (modes 1–10) | confirmed |
| `0x06` | Opening & Closing | 7 (modes 57–63) | not yet |
| `0x07` | Chasing | 10 (modes 21–30) | confirmed |
| `0x08` | Waving (Float) | 10 (modes 11–20) | confirmed |
| `0x0C` | Running (Rainbow) | 13 (modes 64–76) | not yet |
| `0x0D` | Static (custom color) | custom mode | confirmed |

Mode `0x00` is the custom sequence mode — used when building a multi-color
sequence in the app's custom editor. Mode `0x0D` is the custom/manual mode
that activates when setting a single color from the color wheel.

Each UI preset specifies: mode hex, direction, colors, and speed. The
controller only implements 7+1 animation algorithms; the "76 patterns" are
just preset parameter combos.

### Ship & Car modes (other products, not N8H-1AF)

These apply to `lightType=1` products (rock lights, etc.) and use the B2/C2
color protocol instead of A2/A3.

| Hex | Name |
|-----|------|
| `0x01` | Stacking |
| `0x05` | Flow water |
| `0x06` | Draw Curtain |
| `0x07` | Chasing |
| `0x08` | Float |
| `0x0F` | Shuttle |
| `0x10` | Rebound |
| `0x11` | Fixed |

> Note: Some hex values overlap between Dream and Ship & Car (0x01, 0x05–0x08)
> but the animation names differ slightly. The underlying algorithms may or may
> not be the same. `[?]`

## Command Sequencing

### Set color + mode (full update)

Sent as a burst with ~15-20ms between packets:

	A2 → [A3 if >6 colors] → [A4 if >12 colors] → A1

The app often sends this sequence 2-3 times redundantly.

### Toggle on/off or change brightness

	A0

Sent alone.

### Mode change

Observed sequence:

	AD → AE → A0 → A2 → [A3] → A1

The AD/AE pair appears to precede mode transitions. `[?]`

## Protocol Variants (from source, not applicable to N8H-1AF)

The app contains a second protocol for "Ship & Car" light products using
commands B2 and C2 instead of A2/A3. These were **not observed** in captures
from the N8H-1AF.

- **B2**: 14 RGB color slots for zone 1 (44 bytes)
- **C2**: 14 RGB color slots for zone 2 (44 bytes)
- Sequencing: B2 → C2 → A1

## Open Questions

- [x] ~~Transition time~~ → **Speed**: range 1-100, confirmed by slider sweep
- [x] ~~Speed range~~ → 1-100 confirmed
- [x] ~~AD command~~ → streamer length query/set. N8H-1AF default = 70, range at least 70-120
- [x] ~~Direction `0x02`~~ → cycle (both directions). Confirmed by toggling forward/backward/cycle in app
- [ ] Background color (A1 bytes 9-11): always `000000` — when is it used?
- [ ] A0 byte 5: probably strobe rate/mode (RCU has Strobe+/- buttons). `0x1E`(30) observed — test after dark
- [ ] AE command: exact purpose and valid parameter values
- [x] ~~A4 command~~ → colors 12-13 (8 bytes, not zero-padded). App caps at 14 colors total. Confirmed in capture
- [x] ~~Mode `0x0D` vs `0x11`~~ → different products. `0x0D` = Dream light custom/static. `0x11` = Ship & Car Fixed
- [ ] A1 byte 7 ("mode speed"): `0x64` in static, `0x00` in effects — relationship to A0 speed?
- [ ] Does the controller send any responses/notifications? (app subscribes to FFF1 notify)
