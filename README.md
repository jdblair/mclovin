# McLovin

Reverse engineering the Mictuning camper light controller Bluetooth protocol
to build a custom controller.

## Background

Mictuning sells LED light kits for vehicles/campers with a Bluetooth controller
and Android app. The goal is to understand the protocol and replace the stock
app with our own controller.

## APK Details

- **App**: Mictuning light controller
- **Android package**: `com.qunchen.headlightSpp`
- **Internal package**: `com.qunchen.ble.miconline`
- **Transport**: Bluetooth SPP (Serial Port Profile) — classic Bluetooth, not BLE
- **Developer**: Qunchen (OEM behind the Mictuning-branded app)

## Project Structure

- `mictuning.apk` — original APK pulled from phone
- `mictuning-src/` — decompiled Java source (via jadx)
- `jadx/` — jadx decompiler tool

## Hardware

- **Controller ID**: N8H-1AF

## Key Source Files

Decompiled sources of interest under `mictuning-src/sources/com/qunchen/ble/miconline/`:

- `shipAndCarLight/utils/BlueDataSendUtils.java` — Bluetooth command construction
- `shipAndCarLight/event/` — event types (ColorEvent, BaseEvent)
- `shipAndCarLight/activity/` — UI activities for light control
- `shipAndCarLight/bean/CarAndShipControlData.java` — control data structures
- `base/BaseBleActivity.java` — base Bluetooth activity
