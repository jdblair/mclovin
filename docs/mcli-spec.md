# mcli — CLI Specification

## Invocation

```
mcli [GLOBAL OPTIONS] COMMAND [ARGS] [COMMAND [ARGS] ...]
```

Multiple commands on one line share a single BLE connection. Commands execute
left-to-right, sequentially.

## Global Options

| Flag              | Arg     | Default      | Description                    |
|-------------------|---------|--------------|--------------------------------|
| `-a`, `--address` | MAC     | scan by name | Skip scanning, connect directly |
| `-t`, `--timeout` | seconds | 10           | BLE scan/connect timeout       |
| `-v`, `--verbose` |         | off          | Debug logging (shows TX hex)   |

## Commands

**`on`** `[-b BRIGHTNESS] [-s SPEED] [--save]`
Turn lights on. Defaults: brightness=255, speed=1.

**`off`** `[--save]`
Turn lights off.

**`brightness`** `VALUE [--save]`
Set brightness (2-255).

**`speed`** `VALUE [--save]`
Set animation speed (1-100).

**`mode`** `MODE [-s SPEED] [-b BRIGHTNESS] [-d DIRECTION] [--bg RRGGBB] COLOR [COLOR ...]`
Set animation mode with colors. Sends A2 (+ A3 if >6 colors), then A1. If no
colors given, defaults to white. Direction accepts `forward`/`backward` or
`0`/`1`.

**`length`** `[VALUE]`
With no argument: query and print current streamer length. With argument: set
it.

**`raw`** `HEXBYTES`
Send raw bytes (caller computes checksum).

## `--save` flag

Controls the save byte (byte 6) in the A0 packet. By default, `save=0` is
sent and the controller applies the change in RAM only — it reverts to the
last saved state on the next power cycle. With `--save`, `save=1` is sent
and the controller writes the current state to flash, persisting across
power cycles.

The default avoids unnecessary flash writes on the controller. Use `--save`
when you want a setting to stick. Only the `on`, `off`, `brightness`, and
`speed` commands support this flag — `mode` sends an A1 packet, which has no
save field.

## Mode names

Accepted names (case-insensitive): `running_cycle`, `tailing`, `watering`,
`opening_closing`, `chasing`, `waving`, `running_rainbow`, `static`. Short
aliases: `cycle`, `water`, `rainbow`. Raw hex/decimal also accepted (`0x07`,
`13`).

## Color format

6-character hex, optional `#` prefix: `ff0000`, `#00ff00`.

## Command chaining

The argv is split at command keywords. Everything before the first command
keyword is global options. Each command group runs in sequence over the same
connection.

```
mcli -a AA:BB:CC:DD:EE:FF on -b 128 mode chasing ff0000 00ff00 0000ff
```

This connects once, runs `on -b 128`, then `mode chasing ff0000 00ff00 0000ff`,
then disconnects.

## Errors

Bad arguments print to stderr and exit non-zero. Connection failures raise with
bleak's error message. If a command fails mid-chain, subsequent commands don't
run (the connection is still cleaned up).

## Examples

```sh
mcli on
mcli off
mcli on -b 128 -s 50
mcli brightness 200
mcli brightness 50 --save
mcli speed 75
mcli mode static ff0000
mcli mode chasing ff0000 00ff00 0000ff
mcli mode waving -d backward -s 75 ff0000 00ff00
mcli mode rainbow -b 200 ff0000 00ff00 0000ff ffff00 00ffff ff00ff
mcli mode static --bg 101010 ffffff
mcli length
mcli length 90
mcli raw a0010001ff0001a2
mcli -a AA:BB:CC:DD:EE:FF on
mcli -v on brightness 128 mode chasing ff0000 00ff00
```
