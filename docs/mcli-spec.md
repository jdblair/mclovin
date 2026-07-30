# mcli — CLI Specification

## Invocation

```
mcli [GLOBAL OPTIONS] COMMAND [ARGS] [COMMAND [ARGS] ...]
mcli [GLOBAL OPTIONS] repl
```

Multiple commands on one line share a single BLE connection. Commands execute
left-to-right, sequentially. The `repl` subcommand starts an interactive
session (see [REPL Mode](#repl-mode) below).

## Global Options

| Flag              | Arg     | Default      | Description                    |
|-------------------|---------|--------------|--------------------------------|
| `-a`, `--address` | MAC     | scan by name | Skip scanning, connect directly |
| `-t`, `--timeout` | seconds | 10           | BLE scan/connect timeout       |
| `-v`, `--verbose` |         | off          | Debug logging (shows TX hex)   |

## Commands

All commands support `-h`/`--help` to show usage and accepted values.

**`on`** `[-b BRIGHTNESS] [-s SPEED] [--save]`
Turn lights on. Defaults: brightness=255, speed=1.

**`off`** `[--save]`
Turn lights off.

**`brightness`** `VALUE [--save]`
Set brightness (1-255).

**`speed`** `VALUE [--save]`
Set animation speed (1-100).

**`mode`** `MODE [-s SPEED] [-b BRIGHTNESS] [-d DIRECTION] [--bg RRGGBB] COLOR [COLOR ...]`
Set animation mode with colors (1-14). Sends A2 (+ A3 if >6 colors, + A4 if
>12 colors), then A1. If no colors given, defaults to white. Direction accepts `forward`/`backward` or
`0`/`1`. For `static` mode, direction is forced to `0x02` regardless of what
the user passes. Use `mode -h` to list all mode names.

**`length`** `[VALUE]`
With no argument: query and print current streamer length. With argument: set
it.

**`raw`** `HEXBYTES`
Send raw bytes (caller computes checksum).

**`scan`**
List nearby controllers. Does not require a connection.

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

---

## REPL Mode

```
mcli [GLOBAL OPTIONS] repl
```

Starts an interactive REPL that keeps the BLE connection open across
commands. Reuses the same global options as one-shot mode.

### Connection Lifecycle

If `--address` is given, the REPL connects on startup and prints the
connected address. If `--address` is omitted, the REPL starts disconnected
— use the `connect` command to establish a connection.

On exit (via `quit`, `exit`, or Ctrl-D), the REPL disconnects if connected.

### Prompt

```
mcli> _               # when disconnected
mcli [DD:EE]> _       # when connected (last 2 octets of MAC)
```

### Command Syntax

Same as CLI commands, minus the `mcli` prefix. Command chaining works as
in one-shot mode — multiple commands on one line execute left-to-right.

```
mcli> on -b 128
mcli> mode chasing ff0000 00ff00 0000ff
mcli> brightness 100 speed 50
```

Commands that require a connection (`on`, `off`, `brightness`, `speed`,
`mode`, `length`, `raw`) print an error if no connection is active.

### REPL-Only Commands

| Command                      | Description                                |
|------------------------------|--------------------------------------------|
| `connect [ADDRESS]`          | Scan and connect (or connect to ADDRESS)   |
| `disconnect`                 | Disconnect from the controller             |
| `status`                     | Print connection state and address          |
| `help`                       | Print available commands                   |
| `quit` / `exit`              | Disconnect and exit                        |

`connect` without an address scans for a device using the same logic as
one-shot mode (find first device matching name filter, using `--timeout`).

`connect` when already connected prints an error — disconnect first.

`status` output:

```
Connected to AA:BB:CC:DD:EE:FF
```
or
```
Disconnected
```

### Line Editing, History, and Tab Completion

Uses Python `readline` (stdlib) for line editing, history, and tab
completion. No new dependencies.

History is saved to `~/.mcli_history` and loaded on startup. History
file is created if it doesn't exist.

Tab completion is context-aware:

- **First token**: completes command names (`on`, `off`, `brightness`,
  `speed`, `mode`, `length`, `raw`, `scan`, `connect`, `disconnect`,
  `status`, `help`, `quit`, `exit`)
- **After `mode`**: completes mode names (`static`, `chasing`, `rainbow`,
  etc.)
- **After `-d`/`--direction`**: completes `forward`, `backward`

Pressing tab on an empty line or with no matches does nothing (no dump
of all possibilities).

### Error Handling

Errors (bad arguments, BLE failures, `ValueError` from the library) print
to stderr but do **not** exit the REPL loop. The user gets the prompt
back and can retry or try something else.

```
mcli> brightness 999
error: brightness must be 1-255, got 999
mcli>
```

Connection loss mid-session prints an error and resets state to
disconnected. The user can `connect` again.

### Signals

| Signal | Behavior                                         |
|--------|--------------------------------------------------|
| Ctrl-C | Cancel current input line, print fresh prompt    |
| Ctrl-D | Disconnect (if connected) and exit               |

Ctrl-C during a running command (e.g. a slow BLE operation) cancels that
command and returns to the prompt. It does not disconnect.

### Implementation Notes

The REPL reuses the same command parsers and runners from `mcli.py`
(`split_argv`, `COMMAND_PARSERS`, `COMMAND_RUNNERS`). REPL-only commands
(`connect`, `disconnect`, `status`, `help`, `quit`/`exit`) are handled
before the line reaches the existing command-chaining logic.

The `scan` command works in the REPL without a connection, same as in
one-shot mode.

### REPL Examples

```
$ mcli repl
mcli> connect
Scanning... found N8H-1AF (AA:BB:CC:DD:EE:FF)
Connected to AA:BB:CC:DD:EE:FF
mcli [DD:EE]> on -b 128
mcli [DD:EE]> mode chasing ff0000 00ff00 0000ff
mcli [DD:EE]> brightness 200
mcli [DD:EE]> status
Connected to AA:BB:CC:DD:EE:FF
mcli [DD:EE]> disconnect
Disconnected
mcli> quit
```

```
$ mcli -a AA:BB:CC:DD:EE:FF -v repl
Connected to AA:BB:CC:DD:EE:FF
mcli [DD:EE]> on
DEBUG: TX: a0010001ff000142
mcli [DD:EE]> off
DEBUG: TX: a0000001ff000141
mcli [DD:EE]>           # Ctrl-D
Disconnected
```
