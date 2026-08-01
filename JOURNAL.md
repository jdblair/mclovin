# michacking Journal

## 2026-07-27 — Project setup and APK extraction

### What we did

1. **Identified the app** — The Mictuning light controller app isn't published
   under "mictuning". Found it by searching for light/LED related packages:
   `com.qunchen.headlightSpp` (developer: Qunchen).

2. **Extracted the APK** via adb:
   - Enabled USB debugging on phone
   - `adb shell pm list packages --user 0` to find the package
   - `adb shell pm path` revealed a split APK (base + arm64, language, density splits)
   - Pulled `base.apk` — that's sufficient for decompilation

3. **Decompiled with jadx** (v1.5.5):
   - Downloaded from GitHub releases (not in Ubuntu repos)
   - Requires Java (OpenJDK 25 was already installed)
   - Decompiled to `mictuning-src/` — 32 errors out of 7973 classes (normal)

### Key findings

- **Bluetooth transport**: The app supports both SPP and BLE. Despite the package
  name `headlightSpp`, the N8H-1AF controller actually connects via **BLE**
  (confirmed by HCI snoop capture — all traffic is ATT writes to handle 0x0018).
  The app detects transport mode from `BluetoothDevice.getType()`:
  `bluetoothMode == 1` = SPP, `== 2` = BLE.
- **Interesting source paths**:
  - `com/qunchen/ble/miconline/shipAndCarLight/utils/BlueDataSendUtils.java` — command construction
  - `com/qunchen/ble/miconline/shipAndCarLight/event/ColorEvent.java` — color events
  - `com/qunchen/ble/miconline/shipAndCarLight/bean/CarAndShipControlData.java` — data structures
  - `com/qunchen/ble/miconline/shipAndCarLight/activity/` — UI activities

### Next steps

- ~~Read `BlueDataSendUtils.java` to understand command framing and byte protocol~~
- ~~Identify command types: on/off, color, brightness, modes~~
- ~~Look for checksums or framing bytes~~
- ~~Capture actual Bluetooth traffic (HCI snoop log) to cross-reference~~
- Consider nRF Connect or similar for live device exploration

## 2026-07-27 — Protocol analysis from decompiled source

### Source files analyzed

- `BlueDataSendUtils.java` — thin dispatcher, delegates to `CarAndShipControlData` for
  packet construction and `ControlUtil.sendFFF1Spp()` for transport
- `CarAndShipControlData.java` — builds hex strings for the "Ship & Car" protocol variant
  (commands B2, C2, A1, A0 — 14 colors per channel, two zones)
- `ControlUtil.java` — transport layer + "Dream light" protocol variant (commands A2, A3, A1, A0)
- `ShipAndCarLightActivity.java` — UI: seekbars, color pickers, mode buttons

### Two protocol variants in the app

The app has two code paths depending on product type (`ProductKt.isDreamLightType()`):

1. **Ship & Car lights** — uses B2/C2 for colors (14 slots, two zones), via
   `CarAndShipControlData` and `BlueDataSendUtils`
2. **Dream lights** — uses A2/A3 for colors (up to 18 slots across two packets),
   via `ControlUtil.sendDreamColor()` and `sendDreamModel()`

Both share the same A0 (on/off) and A1 (mode/control) commands.

**Checksum**: Last byte of every packet = sum of all preceding bytes mod 256.
Two implementations exist (`makeChecksum` in CarAndShipControlData, `getCheckCode`
in ControlUtil) — both identical: `sum(bytes) & 0xFF`.

#### Modes (from source)

| Name | Hex |
|------|-----|
| Stacking | `0x01` |
| Flow water | `0x05` |
| Draw Curtain | `0x06` |
| Chasing | `0x07` |
| Float | `0x08` |
| Shuttle | `0x0F` |
| Rebound | `0x10` |
| Fixed | `0x11` |

## 2026-07-27 — HCI snoop capture and protocol validation

### Capture setup

- Enabled "Bluetooth HCI snoop log socket" in Android developer options
- Streamed from socket via `adb forward tcp:8872 tcp:8872` + `nc`
- Captured with Wireshark
- Test sequence: set red, blue, green, slid around color wheel, changed modes
  through to Chasing (mode 29 in UI), turned off

### Key discovery: N8H-1AF uses BLE, not SPP

Despite the package name `headlightSpp`, the N8H-1AF controller connects via **BLE**.
All captured traffic is ATT Write Commands to handle `0x0018` (FFF1 characteristic).
The controller is identified as a "Dream light" product, so it uses the A2/A3
color protocol, not B2/C2.

### Validated protocol (from capture)

#### Command A0 — On/off + brightness (8 bytes)

    A0 [on/off] [time_hi time_lo] [brightness] 00 [save] [checksum]

| Offset | Field | Range | Notes |
|--------|-------|-------|-------|
| 0 | Command | `0xA0` | |
| 1 | On/Off | `0x00`/`0x01` | |
| 2-3 | Transition time | 16-bit BE | observed: `0001` |
| 4 | Brightness | 0-255 | confirmed: `0xFF`=max, `0xBD`=189 |
| 5 | Reserved | `0x00` | always zero in capture |
| 6 | Save flag | `0x00`/`0x01` | `01`=persist across power cycles |
| 7 | Checksum | | |

Observed examples:
- Turn on:  `a0 01 00 01 ff 00 01 a2`
- Turn off: `a0 00 00 01 ff 00 01 a1`

#### Command A2 — Color list (20 bytes)

    A2 [R0G0B0] [R1G1B1] ... [R5G5B5] [checksum]

- Up to 6 RGB colors (3 bytes each), unused slots = `000000`
- Fixed 20 bytes: 1 cmd + 18 color data + 1 checksum
- For >6 colors, overflow goes into A3

Observed examples:
- Single red:    `a2 fd0000 000000 000000 000000 000000 000000 9f`
- Single blue:   `a2 0001fb 000000 000000 000000 000000 000000 9e`
- Single green:  `a2 00ff01 000000 000000 000000 000000 000000 a2`
- 3-color chase: `a2 ff0000 0000ff 00ff00 000000 000000 000000 9f`

#### Command A3 — Color overflow (20 bytes)

    A3 [R6G6B6] [R7G7B7] ... [R11G11B11] [checksum]

Same structure as A2. Only sent when >6 colors are active.

Observed: `a3 ffffff 000000 000000 000000 000000 000000 a0` (7th color = white)

#### Command A1 — Mode + control (13 bytes)

    A1 [mode] [dir] [on/off] [time_hi time_lo] [brightness] [speed] [color_count] [bgR bgG bgB] [checksum]

| Offset | Field | Range | Notes |
|--------|-------|-------|-------|
| 0 | Command | `0xA1` | |
| 1 | Mode | see table | `0x0D` = single-color static |
| 2 | Direction | `0x00`/`0x01`/`0x02` | 0=fwd, 1=bwd, 2=seen in single-color mode |
| 3 | On/Off | `0x00`/`0x01` | |
| 4-5 | Transition time | 16-bit BE | observed: `0001` |
| 6 | Brightness | 0-255 | `0xFF` = max |
| 7 | Speed | 0-100? | `0x64`(100) in static, `0x00` in effects |
| 8 | Color count | | number of active colors |
| 9-11 | Background RGB | | `000000` in all observed |
| 12 | Checksum | | |

Observed examples:
- Static red:      `a1 0d 02 01 0001 ff 64 01 000000 16`
- Flow water fwd:  `a1 05 00 01 0001 ff 00 03 000000 aa`
- Flow water bwd:  `a1 05 01 01 0001 ff 00 03 000000 ab`
- Float 7-color:   `a1 08 00 01 0001 ff 00 07 000000 b1`
- Chasing fwd:     `a1 07 00 01 0001 ff 00 03 000000 ac`
- Chasing bwd:     `a1 07 01 01 0001 ff 00 03 000000 ad`

#### Additional commands observed

| Command | Example | Purpose |
|---------|---------|---------|
| `0xAD` | `ad 00 ad` | Streamer count query/set |
| `0xAE` | `ae 00 ae` | Unknown (sent after AD, before mode changes) |
| `0x01` | `01 00` | Notification enable (ATT, not app protocol) |

#### Modes observed in capture

| Name | Hex | Confirmed |
|------|-----|-----------|
| Flow water | `0x05` | yes |
| Chasing | `0x07` | yes |
| Float | `0x08` | yes |
| Single-color static | `0x0D` | yes (not in Ship & Car mode list) |

Mode `0x0D` was not in the `CarAndShipControlData` mode list — it appears to be
specific to the Dream light product type.

#### Sequencing (confirmed)

- **Color + mode update**: A2 → (A3 if >6 colors) → A1 — sent as a burst,
  each packet ~15-20ms apart. Often sent 2-3 times redundantly.
- **On/off only**: A0 alone
- **Mode change**: preceded by AD + AE commands

### Answered questions

- **Brightness range**: 2-255 (confirmed by slider sweep in speed.log)
- **Transport**: BLE for N8H-1AF, not SPP
- **Protocol variant**: Dream light (A2/A3), not Ship & Car (B2/C2)
- **Speed field**: byte 7 of A1 is speed, not reserved (100=static, 0=animated)
- **Direction values**: 0=forward, 1=backward, 2=used in single-color/static mode
- **A0 bytes 2-3 = speed** (not transition time!) — range 1-100, confirmed by slider sweep
- **AD command = LED count query** — N8H-1AF responds with 70 LEDs (0x46)

### Open questions

- Mode `0x0D`: is this the same as Fixed (`0x11`) or distinct?
- AE command: purpose still unknown
- A0 byte 5: usually `0x00`, was `0x1E` in one state restore
- Background color: never non-zero in capture, need to test

### Next steps

- Build a minimal Python BLE script to send commands using `bleak`
- Test setting transition time and speed via the UI to observe range
- Test background color feature
- Map remaining modes (Stacking, Draw Curtain, Shuttle, Rebound)

## 2026-07-28 — Logcat protocol tracing

### Discovery: app logs all commands to logcat

The decompiled source shows extensive `Log.e()` calls throughout the protocol stack:

- **`SPPManager.java:260`** — logs every outgoing SPP command as hex: `"spp writeData>>>" + bytes2HexString()`
- **`SPPManager.java:472`** — logs every incoming response as hex
- **`ControlUtil.java:751`** — logs hex command string at `"sendFFF1Spp: "`
- **`ControlUtil.java:1334-1336`** — logs BLE writes as `"writeBleData"` tag with UUID and hex data

All logging uses `Log.e()` (error level), so it appears even at the default "info" log level.

### Live capture via logcat

Capturing is simple:
```bash
adb logcat | grep writeBleData
```

This gives timestamped hex dumps of every command, e.g.:
```
07-28 08:46:14.809  E TAG     : writeBleData: A0000001000500A6
07-28 08:46:14.809  E writeBleData: UUID=0003cbbb-0000-1000-8000-00805f9bfff1 data=A0000001000500A6
```

Much cleaner than parsing btsnoop binary. For a fresh capture:
```bash
adb logcat -c && adb logcat TAG:E writeBleData:E *:S | tee capture.log
```

### Initial logcat capture: connect → off → on

Captured the app connecting to the controller, then tapping "off" then "on" (lightbulb icon).

**BLE characteristic UUID**: `0003cbbb-0000-1000-8000-00805f9bfff1`

**Unique commands observed** (with frequency):

| Count | Command | Notes |
|-------|---------|-------|
| 104 | `A0 00 00 01 00 05 00 A6` | Polling/status query (~70ms interval) |
| 13 | `A1 0D 02 00 00 01 00 00 01 00 00 00 B2` | Mode state (off state?) |
| 5 | `A2 FF 00 00 ...00 A1` | Color: Red |
| 5 | `A2 00 00 FF ...00 A1` | Color: Blue |
| 4 | `A2 00 FF 00 ...00 A1` | Color: Green |
| 3 | `A2 FF 00 00 00 00 FF 00 FF ...00 9F` | Multi-color (R + slots 2,3) |
| 3 | `A1 07 00 01 00 01 FF 00 03 00 00 00 AC` | Mode: Chasing, 3 colors |
| 2 | `A0 01 00 01 FF 00 01 A2` | On (brightness 0xFF) |
| 2 | `A0 00 00 01 FF 00 01 A1` | Off |
| 1 | `A1 0D 02 01 00 01 96 00 01 00 00 00 49` | Mode: static, brightness 0x96 (150) |
| 1 | `A0 01 00 01 40 07 00 E9` | On with brightness 0x40 (64), transition 7 |

**Key observations**:
- The `A0` polling command (`A0 00 00 01 00 05 00`) is sent constantly as a heartbeat,
  distinct from the on/off A0 commands which have byte 6 = `01` (save flag)
- The polling A0 has a different structure: byte 4 = `05` and byte 6 = `00` (no save),
  while the control A0 has byte 4 = brightness and byte 6 = `01` (save)
- The app sends color (A2) + mode (A1) bursts even during on/off, presumably to
  restore the last active color/mode
- Multi-color `A2 FF 00 00 00 00 FF 00 FF` has colors at positions 0 (red), 2 (blue),
  3 (green?) — suggests the controller was remembering a previous multi-color config

### Revised A0 understanding

~~There appear to be two distinct A0 uses~~ — superseded by speed.log capture below.

### Clean capture: start → connect → off → on → off

Captured with `adb logcat -c && adb logcat TAG:E writeBleData:E *:S` while
performing: open app, connect to N8H-1AF, tap off, tap on, wait.

#### Connection sequence (08:51:35 → 08:51:36)

1. App reports device state: `onOff=0` (off initially)
2. `connectControl` — BLE connection initiated
3. `onConnectState: true` — connected to N8H-1AF
4. `sendP2dFFFA_Cmd: F800` — status query sent to **FFFA** characteristic (not FFF1)
5. Device reports `onOff=1` (actually on)
6. `sendP2dFFFA_Cmd: F100` — state query (220ms later)

#### AE command (08:51:50, ~14s after connect)

`sendFFF1Spp: AE 00 AE` — sent on FFF1, purpose still unclear (sync/ping?)

#### Off command (08:51:55)

```
A0 00 00 01 FF 00 01 A1
```
- byte 1: `00` = off
- byte 4: `FF` = brightness (remembered)
- byte 6: `01` = save

#### On command (08:52:00, ~5s later)

```
A0 01 00 01 FF 00 01 A2
```
- byte 1: `01` = on
- byte 4: `FF` = brightness
- byte 6: `01` = save

#### Post-on query (08:52:09, ~9s later)

`sendP2dFFFA_Cmd: F100` — another F1 state query on FFFA

#### Key findings

1. **On/off is a single A0 command** — no A1/A2 bursts needed, just 8 bytes
2. **No heartbeat polling** in this capture — the `A0 00 00 01 00 05 00` flood
   from the earlier capture was likely a different app state (maybe the color
   picker view sends continuous polls)
3. **Two BLE characteristics**:
   - **FFF1** (`0003cbbb-0000-1000-8000-00805f9bfff1`) — command channel
     (A0, A1, A2, AE, etc.)
   - **FFFA** — query channel (`F800` = status query, `F100` = state query).
     Responses likely come back via BLE notifications
4. **F8/F1 are queries, not commands** — `F800` sent on connect (initial status),
   `F100` sent periodically to poll current state
5. **The app logs in Chinese** — `普通` ("normal/standard") tags the BLE code path
   vs SPP; `查询` ("query") marks status queries; `看看有没有被我覆盖` ("let me
   check if I've been overwritten") is a debug message in the broadcast receiver

### Speed + brightness capture: connect → chasing R/G/B → speed sweep → brightness sweep → off

Captured with `adb logcat -c && adb logcat TAG:E writeBleData:E *:S | tee speed.log`.
Actions: connect, set R/G/B Chasing Forward (mode 29 in UI), adjust speed slider
max→min→max, adjust brightness slider max→min→max, tap off.

#### AD response confirms LED count

- Sent: `AD 00 AD`
- Response: `AD 46 F3` — 0x46 = **70 LEDs**

#### Speed slider sweep (09:38:57 → 09:39:09)

Byte 3 of A0 changes while brightness (byte 4) stays `0xFF`:

```
A0 01 00 03 FF 00 00 A3   speed=3    (increasing)
A0 01 00 05 FF 00 00 A5   speed=5
...
A0 01 00 64 FF 00 00 04   speed=100  (MAX)
A0 01 00 64 FF 00 01 05   speed=100  save=1 (slider released)
  [pause ~2s]
A0 01 00 62 FF 00 00 02   speed=98   (decreasing)
...
A0 01 00 03 FF 00 00 A3   speed=3
A0 01 00 01 FF 00 01 A2   speed=1    save=1 (MIN, slider released)
```

**Speed range: 1–100 (0x01–0x64)**. What we previously called "transition time"
is actually speed. Byte 2 is always 0x00 (high byte of 16-bit speed, unused since
max=100).

#### Brightness slider sweep (09:39:11 → 09:39:19)

Byte 4 changes while speed (byte 3) stays at `0x01`:

```
A0 01 00 01 FA 00 00 9C   brightness=250  (decreasing)
...
A0 01 00 01 02 00 00 A4   brightness=2    (MIN)
  [pause ~1s]
A0 01 00 01 03 00 00 A5   brightness=3    (increasing)
...
A0 01 00 01 FF 00 01 A2   brightness=255  save=1 (MAX, slider released)
```

**Brightness range: 2–255 (0x02–0xFF)**.

#### Save flag behavior

- `save=0` while slider is being dragged (live update, no flash write)
- `save=1` when slider is released (persist final value)
- Smart design to minimize flash wear on the controller

#### Revised A0 command format

```
A0 [on/off] [speed_hi] [speed_lo] [brightness] [??] [save] [checksum]
```

| Offset | Field | Range | Notes |
|--------|-------|-------|-------|
| 0 | Command | `0xA0` | |
| 1 | On/Off | 0/1 | |
| 2-3 | Speed | 16-bit BE, 1–100 | confirmed by slider sweep |
| 4 | Brightness | 2–255 | confirmed by slider sweep |
| 5 | Unknown | usually `0x00` | was `0x1E` (30) in one state restore — separate param? |
| 6 | Save | 0/1 | 0=transient (dragging), 1=persist (released) |
| 7 | Checksum | | |

#### Answered questions from previous session

- **"Transition time" was actually speed** — range 1-100, confirmed
- **Speed range**: 1-100 (not 0-255)
- **Brightness range**: 2-255
- **AD command**: query/set streamer length (see below)

### Streamer length capture (streamer.log)

The AD command is not just a query — it's also used to **set** the streamer
(LED strip) length. This tells the controller how many LEDs to address in
animations.

- `AD 00 AD` = query → device responds `AD 46 F3` (current length = 70)
- `AD [n] [checksum]` = set length to `n`
- Slider swept from 71 (0x47) up to 120 (0x78), then back down to 70 (0x46)
- No save flag — each AD command takes effect immediately

Also confirmed: A0 byte 5 = `0x1E` (30) appears again in the initial state
restore (`A0 00 00 01 BD 1E 00 7C`), consistently non-zero across captures.
Still unknown what it represents.

### Dream light mode table found

The 76 UI patterns are defined in `resources/assets/model.json` in the APK.
They map to only **7 distinct animation algorithms**:

| Hex | Animation | # Presets |
|-----|-----------|-----------|
| `0x01` | Running Cycle | 6 |
| `0x04` | Tailing | 20 |
| `0x05` | Watering (Flow water) | 10 |
| `0x06` | Opening & Closing | 7 |
| `0x07` | Chasing | 10 |
| `0x08` | Waving (Float) | 10 |
| `0x0C` | Running (Rainbow) | 13 |

Each preset is a combination of algorithm + direction + color palette. The
controller only has 7 (or 8 with custom) animation modes; the "76 patterns"
are parameter presets.

Mode `0x0D` (static/custom) is **not** in model.json — it's the custom mode
from the color wheel. The Ship & Car mode table (`CarAndShipControlData`) is
for other products (rock lights etc.) using the B2/C2 protocol.

#### Answered questions

- **Mode `0x0D` vs `0x11`**: different products. `0x0D` = Dream light custom/static,
  `0x11` = Ship & Car "Fixed" mode
- **76 patterns**: 7 algorithms × color/direction presets, not 76 unique mode IDs

### Strobe investigation

The physical RCU has Strobe+/Strobe- buttons not present in the app UI.

**What the code shows**:
- `model.json`: every Dream light preset has a `strobe` field, but it's always 0
- `MpStrobeModeBean` (in `ui/smart/mp/`): 6 strobe modes for the multi-port
  product line (0 = "Full On", 1–5 = "Strobe Mode 2–6")
- `CommonInfoBean`: has a `flash` field (int), default 0 or 5
- `CommandUtil.getRGBCtl()`: builds a 10-byte command with byte 7 = flash value,
  but this is the multi-port command format, not A0/A1
- `LightControlState`: defines `FlashOff`/`FlashOn` (闪烁) and `Pulse1`–`Pulse6`
  states — these are strobe speed levels for multi-port products
- The Flash/Strobe UI buttons only appear in the multi-port activity, not Dream light

**Conclusion**: strobe is a feature of the multi-port product line. The app
doesn't expose it for Dream lights, but the controller firmware likely supports
it natively via the RCU.

**A0 byte 5 = 0x1E (30) — possible strobe parameter?** The mp strobe values
are 0–5 (mode) or 9–20 (pulse states), not 30. Could be a different encoding
for the Dream light protocol. Need to test: capture while pressing Strobe+/-
on the RCU, or send A0 commands with varying byte 5 values after dark.

## 2026-07-29 — Library spec review: open questions

Wrote `docs/mclovin-spec.md` as source-of-truth for the McLovin class API.
Review flagged issues that fall into two buckets: protocol unknowns that need
hardware testing or more APK digging, and spec doc fixes that can be done
anytime.

### Protocol questions (need RE work)

- **Brightness range mismatch**: `on()` allows 1-255 but `set_brightness()`
  requires 2-255. The capture (speed.log) shows the app slider bottoms out
  at 2. Is brightness=1 valid at the wire level? Does it do anything visible,
  or is it effectively off? Test on hardware.

- **`speed` vs `mode_speed` in A1**: A1 byte 4-5 is "speed" (16-bit, range
  1-100), byte 7 is "mode_speed" (8-bit). Static mode uses speed=1,
  mode_speed=0x64; animated modes use speed=N, mode_speed=0x00. The current
  library maps the user-facing `speed` param to A1 bytes 4-5 only. Is byte 7
  a separate control, or is the OEM app just encoding the same value in a
  different slot depending on mode? Check `ControlUtil.sendDreamModel()` more
  carefully.

- **`direction` value 0x02**: capture shows 0x00=fwd, 0x01=bwd, 0x02 in
  static mode. Is 0x02 "both"/"none"/something else? Only seen with mode
  0x0D. Check if other modes accept it.

- **`set_streamer_length` valid range**: capture shows 70-120, but what are
  the real bounds? The slider in the app presumably has min/max — find in
  `ShipAndCarLightActivity` or test on hardware.

- **A1 `speed` field**: the high-level `set_mode()` takes a `speed` param
  mapped to A1 bytes 4-5 (same as A0). But the A0 speed is the animation
  speed slider, and A1 speed might be something else (transition time between
  mode switches?). The captures always show `00 01` in A1 bytes 4-5. Need
  to test: does changing A1 speed actually do anything?

### Spec doc fixes (no RE needed, just editing)

- `scan()` return type annotation: `-> list` should be `-> list[BLEDevice]`
- `set_mode()` parameter table needs a Range column
- `set_streamer_length()` needs a parameter table
- A2/A3 byte-layout tables missing (A0/A1 have them)
- CLI synopsis: `COLOR [COLOR ...]` should be `[COLOR ...]` (optional)
- Note Python 3.10+ requirement (uses `str | None` syntax)

## 2026-07-30 — Custom sequence capture: A4 confirmed, mode 0x00

Captured the app's custom color sequence editor in action (`capture.log`).
Used the app to create a 14-slot sequence of alternating white/black, then
tapped the "check" button to save.

### What the capture shows

The save event sends a burst of 4 packets:

```
A2 FFFFFF 000000 FFFFFF 000000 FFFFFF 000000 99   slots 0-5
A3 FFFFFF 000000 FFFFFF 000000 FFFFFF 000000 9A   slots 6-11
A4 FFFFFF 000000 A1                                slots 12-13
A1 00 02 01 0001 FF 00 0E 000000 B2               mode=0x00, count=14
```

### Key findings

- **A4 packet confirmed**: 8 bytes total (cmd + 2 colors + checksum). NOT
  zero-padded to 20 bytes like A2/A3. Carries only 2 color slots (12-13).
  Total capacity: 6+6+2 = 14 colors max. The source code has room for 6
  slots in A4 (12-17) but the app never fills beyond 2.

- **Mode 0x00 is the custom sequence mode**: distinct from 0x0D (static/
  color wheel). Used with color_count=14 (0x0E). Direction=0x02 in this
  capture (same as static).

- **Live preview behavior**: each time a color slot is tapped in the editor,
  the app immediately sends A2 (single color in slot 0) + A1 (static mode,
  count=1) to preview it. The full A2+A3+A4+A1 burst is only sent on "check."

- **Strobe byte 0x1E**: seen again in an A0 at 07:58:29 during what looks
  like a state restore. Still not clear what triggers it.

- **Mode 0x10**: appeared briefly (lines 15, 26), not in the Dream Light
  mode table. Could be from the Ship & Car mode set (0x10 = "Rebound"),
  possibly sent as part of a cross-mode transition in the app.

### Protocol doc updates

- Added A4 command section with byte layout
- Added mode 0x00 (custom sequence) to mode table
- Updated color_count range from 1-18 to 1-14
- Updated command sequencing to include A4
- Closed the A4 open question

## 2026-07-30 — Direction capture: 0x02 = cycle confirmed

Second capture session (`capture.log`, overwritten). Selected a 4-color
pattern (red, green, blue, violet) in mode 0x10 and cycled through the
direction options: forward, backward, cycle, forward, then off.

### Decoded sequence

Colors (same A2 in all bursts):
```
A2 FD0101 01FF01 0101FE 9601FF 000000 000000 38
```
Near-pure R/G/B/violet — app picker uses FD/01 instead of FF/00.

A1 direction changes (mode=0x10, mode_speed=0x64, count=4):
```
A1 10 02 ... DA   initial (cycle)
A1 10 00 ... D8   forward
A1 10 01 ... D9   backward
A1 10 02 ... DA   cycle
A1 10 00 ... D8   forward
```

Off: `A0 00 0001 BD 1E 01 7D`

### Key findings

- **Direction 0x02 = cycle (both directions)**: resolves the open question.
  Not specific to static mode — confirmed with mode 0x10.

- **Mode 0x10 works on N8H-1AF**: despite being listed as "Rebound" in the
  Ship & Car mode table, the N8H-1AF (Dream Light product) accepts it.
  Mode sets are not product-exclusive.

- **Strobe 0x1E is persistent**: present in both the on and off A0 packets,
  so it was saved to flash in a prior session and restored by the app.

- **Connection init sequence**: P2D queries to FFFA (F800, F100), then AE00,
  then AD query (response: length=70). This happens every time the app
  enters the mode control screen.

### Protocol doc updates

- Resolved direction 0x02 → cycle
- Closed the direction open question

## 2026-07-30 — Mode sweep capture + unified mode table

Two more capture sessions. First: tapped all 8 mode buttons in the manual
mode UI (rebound, flow water, chasing, stacking, draw curtain, float,
shuttle, flash) with 4 colors. Second: scrolled through the first few of
the 76 "constant mode" presets (all Flow Water variants).

### Mode sweep results

All modes confirmed working on N8H-1AF with same A2 colors:

| Button | Mode byte |
|--------|-----------|
| rebound | 0x10 |
| flow water | 0x05 |
| chasing | 0x07 |
| stacking | 0x01 |
| draw curtain | 0x06 |
| float | 0x08 |
| shuttle | 0x0F |
| flash | **0x0A** (new) |

Mode 0x0A (Flash) was not in either mode table — now added.

### Preset capture observations

- Presets are parameter combos as expected: same mode 0x05, varying
  direction and color sets. First 3 presets match model.json order.
- mode_speed=0x00 for all presets (vs 0x64 from the manual UI).
- A1 on_off byte = 0x00 in backward preset — lights stayed on, so
  the controller may ignore this byte in A1 context.
- App sends A2+A1 bursts 2-3x redundantly for some preset changes.

### Merged mode table

The "Dream Light" vs "Ship & Car" mode table split in the protocol doc
was misleading — the N8H-1AF accepts modes from both lists. Merged into
a single table. The distinction in the source may refer to color protocols
(A2/A3 vs B2/C2), not mode sets.

## 2026-07-30 — F800/F100 source analysis: P2C status queries

Investigated the F800 and F100 commands sent to FFFA on connection init,
hoping to find a way to read controller state. Result: these are for a
different product family (P2C/P2D devices), not Dream Light.

### What the source shows

`sendP2dFFFA_Cmd()` in ControlUtil.java sends commands to the FFFA
characteristic. On connection init:

1. Open notification on FFFA
2. Send F800 (status query) — responses starting with F8/F9 saved as
   P2C status data via SaveUtils
3. Send F100 (color data query) — F1 response byte 3 is parsed as
   on/off state

P2C12AControlActivity has a polling loop that sends F100/F200/F300/F400/
F800 until all state is populated. This is full state readback — but only
for P2C products.

### Implications for N8H-1AF

The N8H-1AF (Dream Light) uses FFF1 for everything. The capture logs show
no response to F-commands on FFFA — only AD responses on FFF1. There is
no known way to read back mode, color, or brightness state from the
N8H-1AF. The only query command is AD 00 (streamer length).

The app works around this by storing all state locally on the phone and
pushing it to the controller. If you control the light from a different
phone or tool, the app has no way to sync.

## 2026-07-30 — Testing notes

### Length command

The `length` command appears to control the length of the effect, not the
number of LEDs. When set to a value less than the physical strip length,
the remaining LEDs stay lit (holding their last state). Need to experiment
more — is the remaining segment static, or does it just not participate
in animations?

### Controller crash (unreproducible)

Observed once: a subset of LEDs flashed randomly white and the Bluetooth
connection dropped. Was able to reconnect without power cycling (suggests
firmware reboot, not hard lockup). Initial diagnosis was "mode without
colors" but this doesn't hold up — `cmd_mode` always sends A2 (defaulting
to white) before A1, and `set_colors()` rejects empty lists. Unable to
reproduce. Cause unknown.

## 2026-07-31 — CLI feature batch

Implemented five spec changes in a single commit (`1a1af1a`):

1. **`--strobe` on on/off**: Added `--strobe N` flag to both `on` and
   `off` commands. Threads through to `_build_a0()` which already had the
   strobe byte position. Updated `mclovin.py` `on()` and `off()` method
   signatures.

2. **Timeout default 10→5, scan `-t` override**: Global timeout now
   defaults to 5s. `scan` subcommand gets its own `-t`/`--timeout` that
   overrides the global when specified. Both one-shot and REPL scan paths
   updated.

3. **Named colors**: 17 predefined color names (red, green, blue, white,
   cyan, magenta, orange, purple, pink, violet, teal, indigo, coral, gold,
   warmwhite, etc.). `parse_color()` does case-insensitive name lookup
   before hex parse, so both `red` and `ff0000` work. Tab completion
   offers color names after mode name position and after `--bg`.

4. **Multi-device guard**: When scanning discovers >1 controller, one-shot
   mode prints the list and exits with error. REPL `connect` prints the
   list and prompts `connect ADDRESS`. Single device auto-selects as
   before.

5. **REPL `loglevel` command**: `loglevel` shows current level, `loglevel
   debug` sets both root and mclovin loggers. Tab-completes level names.

## 2026-07-31 — Package for GitHub release

Converted the flat `scripts/` layout into a proper installable Python
package and cleaned up the repo for public release.

### Package structure

Created `src/mclovin/` layout with `pyproject.toml`:

- `scripts/mclovin.py` → `src/mclovin/lib.py`
- `scripts/mcli.py` → `src/mclovin/cli.py`
- `src/mclovin/__init__.py` re-exports the public API from `lib.py`
- `pyproject.toml` defines `mcli` console script entry point
- `scripts/demo.py` stays as an example (imports from installed package)

Build backend: `setuptools.build_meta` (the plan had
`setuptools.backends._legacy:_Backend` which doesn't exist).

### Files removed from tracking

- `NOTES.org`, `btsnoop/`, `docs/mclovin.html` — added to `.gitignore`,
  removed from git but kept on disk
- `requirements.txt` — superseded by `pyproject.toml`, deleted
- `scripts/mclovin.py`, `scripts/mcli.py` — moved to `src/mclovin/`
- `scripts/exit` — empty junk file, deleted

### Doc updates

- `README.md` — rewritten for a public audience: background, hardware
  details, contributing section, install/usage instructions
- `CLAUDE.md` — updated paths and status
- `docs/protocol.md` — replaced N8H-1AF references with "test unit"
  and renamed to "Mictuning Dream Light BLE Protocol Spec"
- `docs/mclovin-spec.md` — updated path, removed `DEVICE_NAME` constant
  (removed from library; scan now defaults `name_filter=None`)
- `docs/mcli-spec.md` — updated path reference

### Verified

- `pip install -e .` succeeds in the project `.venv`
- `from mclovin import McLovin` works via `__init__.py`
- `mcli --help` works via `console_scripts` entry point
