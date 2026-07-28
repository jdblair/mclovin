# For Claude Code / AI assistants:

- **Project**: McLovin — reverse engineering Mictuning camper light Bluetooth protocol
- **Goal**: Understand the SPP protocol and build a custom controller
- **Status**: APK decompiled, protocol analysis in progress

## Key Info

- Original APK package: `com.qunchen.headlightSpp`
- Uses Bluetooth Classic SPP (not BLE)
- OEM developer: Qunchen
- Decompiled source in `mictuning-src/`

## Focus Areas

- `mictuning-src/sources/com/qunchen/ble/miconline/shipAndCarLight/` — main control logic
- `BlueDataSendUtils.java` — command byte construction (start here)
- Look for: command framing, checksums, color encoding, mode selection

## Notes

- jadx decompilation had 32 errors out of 7973 classes — minor, most code is readable
- Despite package name mentioning BLE, the app uses SPP (Serial Port Profile)
