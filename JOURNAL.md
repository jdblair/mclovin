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

- **Bluetooth transport**: SPP (Serial Port Profile) — classic Bluetooth serial,
  not BLE. Despite the internal package referencing "ble" (`com.qunchen.ble.miconline`),
  the package name `headlightSpp` confirms SPP.
- **Interesting source paths**:
  - `com/qunchen/ble/miconline/shipAndCarLight/utils/BlueDataSendUtils.java` — command construction
  - `com/qunchen/ble/miconline/shipAndCarLight/event/ColorEvent.java` — color events
  - `com/qunchen/ble/miconline/shipAndCarLight/bean/CarAndShipControlData.java` — data structures
  - `com/qunchen/ble/miconline/shipAndCarLight/activity/` — UI activities

### Next steps

- Read `BlueDataSendUtils.java` to understand command framing and byte protocol
- Identify command types: on/off, color, brightness, modes
- Look for checksums or framing bytes
- Capture actual Bluetooth traffic (HCI snoop log) to cross-reference
- Consider nRF Connect or similar for live device exploration
