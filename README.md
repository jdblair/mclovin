# McLovin

Reverse engineering the Mictuning camper light controller Bluetooth protocol
to build a custom controller.

![McLovin's sweet fake ID](./assets/mclovin-id.jpg)

## Background

Mictuning sells LED light kits for vehicles with a Bluetooth controller
and Android app. The goal is to understand the protocol and replace the stock
app with our own controller.

## APK Details

- **App**: Mictuning light controller
- **Android package**: `com.qunchen.headlightSpp`
- **Internal package**: `com.qunchen.ble.miconline`
- **Transport**: BLE (despite package name mentioning SPP)
- **Developer**: Qunchen (OEM behind the Mictuning-branded app)

## Hardware

- **Controller ID**: N8H-1AF

## Project Structure

- `scripts/mclovin.py` — Python BLE control library (McLovin class)
- `scripts/demo.py` — demo script exercising the library
- `scripts/mcli.py` — CLI tool (planned, see spec)
- `docs/protocol.md` — reverse-engineered protocol spec
- `docs/mcli-spec.md` — CLI tool specification
- `docs/chinese-glossary.md` — glossary from decompiled source
- `mictuning-src/` — decompiled Java source (via jadx)
- `btsnoop/` — HCI snoop captures

## Key Source Files

Decompiled sources of interest under `mictuning-src/sources/com/qunchen/ble/miconline/`:

- `shipAndCarLight/utils/BlueDataSendUtils.java` — Bluetooth command construction
- `shipAndCarLight/event/` — event types (ColorEvent, BaseEvent)
- `shipAndCarLight/activity/` — UI activities for light control
- `shipAndCarLight/bean/CarAndShipControlData.java` — control data structures
- `base/BaseBleActivity.java` — base Bluetooth activity
