# McLovin

BLE control library and CLI for Mictuning LED controllers.

![McLovin's sweet fake ID](assets/mclovin-id.jpg)

## Background

Mictuning sells LED light kits for vehicles (underlights, "rock
lights", and others), with a bluetooth controller, remote control, and
mobile device (iOS, Android) apps.  This project implements the
reverse-engineered BLE protocol in a python library and provides a CLI
for using the library.

This project is (so far) based only on the Mictuning underlight kit, and
implements a protocol called "Dream Lights" in the decompiled Android
APK source.

## Details

The Mictuning LED controller is powered by 12V DC and is housed in a
small weatherproof box designed to be mounted under a car. The
underlight kit controls 4 LED light strings split into two strings,
each connected to a port on the controller.

The control protocol does not allow for individual addressing of
LEDs. It instead provides a set of pre-programmed lighting effects
implemented in the controller itself. A list of up to 14 color changes
can be provided for the effect, as well as separate brightness and
"strobe" control.

What is known of the protocol is documented in
[protocol.md](docs/protocol.md).

## Protocol Reverse Engineering Process

The protocol was first examined using Android's HCI snoop
function. The resulting snoop logs can be loaded into Wireshark for
examination.

After decompiling the APK using jadx, I discovered that debugging
messages were left in the production app. The message labeled
writeBleData outputs the raw data sent to the controller. This means
the protocol can be easily observed in real-time using the following
command, at least until Mictuning updates the app and removes these
messages.

`adb logcat -c && adb logcat TAG:E writeBleData:E *:S | tee capture.log`


## Contributing

This is a work in progress. If you have access to a Mictuning light
kit and you would like to contribute, please do!

If you implement a new feature, please include the appropriate
modification to the spec files.


## Install

```sh
pip install .          # or pip install -e . for development
```

## Usage

The `mcli` command is installed as a console script:

```sh
mcli on                         # turn on (auto-scan for controller)
mcli off
mcli on -b 128                  # turn on at half brightness
mcli mode static red            # solid red
mcli mode chasing red green blue -s 50
mcli brightness 200
mcli length                     # query streamer length
mcli -a AA:BB:CC:DD:EE:FF on    # skip scanning, connect by address
mcli repl                       # interactive REPL
```

Multiple commands can be chained on one invocation to share a single
BLE connection:

```sh
mcli on -b 128 mode chasing ff0000 00ff00 0000ff
```

See `mcli --help` and `mcli <command> -h` for full details.

## Library

```python
from mclovin import McLovin, MODE_STATIC

m = McLovin()
devices = await McLovin.scan()
await m.connect(devices[0].address)

await m.set_colors([(255, 0, 0)])
await m.set_mode(MODE_STATIC, color_count=1)

await m.off()
await m.disconnect()
```

## Project Structure

- `src/mclovin/lib.py` — BLE control library (`McLovin` class)
- `src/mclovin/cli.py` — CLI tool (`mcli`)
- `scripts/demo.py` — example script exercising the library
- `docs/protocol.md` — reverse-engineered BLE protocol spec
- `docs/mclovin-spec.md` — library API specification
- `docs/mcli-spec.md` — CLI specification
- `docs/chinese-glossary.md` — glossary from decompiled source
