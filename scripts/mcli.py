#!/usr/bin/env python3
"""mcli — CLI for McLovin BLE LED controller.

Supports command chaining: multiple commands share a single BLE connection.
See docs/mcli-spec.md for full specification.
"""

import argparse
import asyncio
import logging
import os
import readline
import shlex
import sys

from mclovin import McLovin

# --- Constants ---

MODE_LOOKUP = {
    "running_cycle": 0x01, "cycle": 0x01,
    "tailing": 0x04,
    "watering": 0x05, "water": 0x05,
    "opening_closing": 0x06,
    "chasing": 0x07,
    "waving": 0x08,
    "running_rainbow": 0x0C, "rainbow": 0x0C,
    "static": 0x0D,
}

COMMAND_NAMES = {"on", "off", "brightness", "speed", "mode", "length", "raw", "scan"}

# --- Parsers ---


def make_global_parser():
    epilog = """\
commands:
  on             turn lights on
  off            turn lights off
  brightness     set brightness (2-255)
  speed          set animation speed (1-100)
  mode           set animation mode with colors
  length         query or set streamer length
  raw            send raw hex bytes
  scan           list nearby controllers
  repl           interactive REPL (connect once, run many commands)

Multiple commands can be chained on one invocation to share
a single BLE connection (e.g. mcli on -b 128 mode chasing ff0000).
"""
    p = argparse.ArgumentParser(
        prog="mcli",
        description="Control Mictuning LED strips over BLE.",
        usage="mcli [OPTIONS] COMMAND [ARGS] [COMMAND [ARGS] ...]",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-a", "--address", help="BLE MAC address (skip scanning)")
    p.add_argument("-t", "--timeout", type=float, default=10,
                   help="BLE scan/connect timeout in seconds (default: 10)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="enable debug logging (shows TX hex)")
    return p


def make_on_parser():
    p = argparse.ArgumentParser(prog="on", add_help=False)
    p.add_argument("-b", "--brightness", type=int, default=255)
    p.add_argument("-s", "--speed", type=int, default=1)
    p.add_argument("--save", action="store_true")
    return p


def make_off_parser():
    p = argparse.ArgumentParser(prog="off", add_help=False)
    p.add_argument("--save", action="store_true")
    return p


def make_brightness_parser():
    p = argparse.ArgumentParser(prog="brightness", add_help=False)
    p.add_argument("value", type=int)
    p.add_argument("--save", action="store_true")
    return p


def make_speed_parser():
    p = argparse.ArgumentParser(prog="speed", add_help=False)
    p.add_argument("value", type=int)
    p.add_argument("--save", action="store_true")
    return p


def make_mode_parser():
    p = argparse.ArgumentParser(prog="mode", add_help=False)
    p.add_argument("mode_name")
    p.add_argument("-s", "--speed", type=int, default=1)
    p.add_argument("-b", "--brightness", type=int, default=255)
    p.add_argument("-d", "--direction", default="forward")
    p.add_argument("--bg", default="000000")
    p.add_argument("colors", nargs="*")
    return p


def make_length_parser():
    p = argparse.ArgumentParser(prog="length", add_help=False)
    p.add_argument("value", nargs="?", type=int, default=None)
    return p


def make_raw_parser():
    p = argparse.ArgumentParser(prog="raw", add_help=False)
    p.add_argument("hexbytes")
    return p


def make_scan_parser():
    return argparse.ArgumentParser(prog="scan", add_help=False)


COMMAND_PARSERS = {
    "on": make_on_parser,
    "off": make_off_parser,
    "brightness": make_brightness_parser,
    "speed": make_speed_parser,
    "mode": make_mode_parser,
    "length": make_length_parser,
    "raw": make_raw_parser,
    "scan": make_scan_parser,
}

# --- Helpers ---


def parse_color(s: str) -> tuple[int, int, int]:
    """Parse a hex color string like 'ff0000' or '#ff0000'."""
    s = s.lstrip("#")
    if len(s) != 6:
        raise argparse.ArgumentTypeError(f"bad color '{s}': expected 6 hex digits")
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        raise argparse.ArgumentTypeError(f"bad color '{s}': invalid hex")


def parse_mode(s: str) -> int:
    """Resolve a mode name, alias, or numeric value to a mode byte."""
    key = s.lower()
    if key in MODE_LOOKUP:
        return MODE_LOOKUP[key]
    # Try as integer (decimal or 0x hex)
    try:
        return int(s, 0)
    except ValueError:
        names = ", ".join(sorted(MODE_LOOKUP.keys()))
        raise argparse.ArgumentTypeError(
            f"unknown mode '{s}'. Valid names: {names}")


def parse_direction(s: str) -> int:
    """Parse direction: forward/0 or backward/1."""
    lookup = {"forward": 0, "0": 0, "backward": 1, "1": 1}
    key = s.lower()
    if key not in lookup:
        raise argparse.ArgumentTypeError(
            f"bad direction '{s}': expected forward/backward or 0/1")
    return lookup[key]


def split_argv(argv: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Split argv into global options and a list of (command_name, args) groups.

    Walks argv left-to-right. Tokens matching COMMAND_NAMES start a new group.
    Everything before the first command is global options.
    """
    global_args = []
    commands = []
    current_cmd = None
    current_args = []

    for token in argv:
        if token in COMMAND_NAMES:
            if current_cmd is not None:
                commands.append((current_cmd, current_args))
            current_cmd = token
            current_args = []
        elif current_cmd is None:
            global_args.append(token)
        else:
            current_args.append(token)

    if current_cmd is not None:
        commands.append((current_cmd, current_args))

    return global_args, commands

# --- Command runners ---


async def cmd_on(m: McLovin, args: argparse.Namespace):
    await m.on(brightness=args.brightness, speed=args.speed, save=args.save)


async def cmd_off(m: McLovin, args: argparse.Namespace):
    await m.off(save=args.save)


async def cmd_brightness(m: McLovin, args: argparse.Namespace):
    await m.set_brightness(args.value, save=args.save)


async def cmd_speed(m: McLovin, args: argparse.Namespace):
    await m.set_speed(args.value, save=args.save)


async def cmd_mode(m: McLovin, args: argparse.Namespace):
    mode = parse_mode(args.mode_name)
    direction = parse_direction(args.direction)
    bg = parse_color(args.bg)

    if args.colors:
        colors = [parse_color(c) for c in args.colors]
    else:
        colors = [(255, 255, 255)]

    await m.set_colors(colors)
    await m.set_mode(
        mode=mode,
        direction=direction,
        speed=args.speed,
        brightness=args.brightness,
        color_count=len(colors),
        bg_color=bg,
    )


async def cmd_length(m: McLovin, args: argparse.Namespace):
    if args.value is None:
        length = await m.get_streamer_length()
        print(length)
    else:
        await m.set_streamer_length(args.value)


async def cmd_raw(m: McLovin, args: argparse.Namespace):
    try:
        data = bytes.fromhex(args.hexbytes)
    except ValueError:
        raise ValueError(f"bad hex string '{args.hexbytes}'")
    await m.send_raw(data)


COMMAND_RUNNERS = {
    "on": cmd_on,
    "off": cmd_off,
    "brightness": cmd_brightness,
    "speed": cmd_speed,
    "mode": cmd_mode,
    "length": cmd_length,
    "raw": cmd_raw,
}

# --- REPL ---

HISTORY_FILE = os.path.expanduser("~/.mcli_history")

ALL_COMMANDS = sorted(list(COMMAND_NAMES) + [
    "connect", "disconnect", "status", "help", "quit", "exit",
])
MODE_NAMES_LIST = sorted(MODE_LOOKUP.keys())
DIRECTIONS = ["backward", "forward"]


def completer(text, state):
    line = readline.get_line_buffer()
    tokens = line[:readline.get_endidx()].split()

    if not tokens or (len(tokens) == 1 and text):
        matches = [c for c in ALL_COMMANDS if c.startswith(text)]
    elif tokens[0] == "mode" and len(tokens) <= 2:
        matches = [m for m in MODE_NAMES_LIST if m.startswith(text)]
    elif len(tokens) >= 2 and tokens[-2] in ("-d", "--direction"):
        matches = [d for d in DIRECTIONS if d.startswith(text)]
    else:
        matches = []

    if state < len(matches):
        return matches[state]
    return None


def setup_readline():
    try:
        readline.read_history_file(HISTORY_FILE)
    except FileNotFoundError:
        pass
    readline.set_history_length(1000)
    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")


async def async_repl(globals_):
    """Run the interactive REPL."""
    m = McLovin()
    addr = None

    setup_readline()

    # Auto-connect if address was given on the command line
    if globals_.address:
        try:
            await m.connect(globals_.address, timeout=globals_.timeout)
            addr = globals_.address
            print(f"Connected to {addr}")
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)

    try:
        while True:
            if addr:
                prompt = f"mcli [{addr[-5:]}]> "
            else:
                prompt = "mcli> "

            try:
                line = input(prompt)
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                continue

            line = line.strip()
            if not line:
                continue

            try:
                tokens = shlex.split(line)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                continue

            verb = tokens[0]

            # REPL-only commands
            if verb == "quit" or verb == "exit":
                break

            elif verb == "status":
                if addr:
                    print(f"Connected to {addr}")
                else:
                    print("Disconnected")
                continue

            elif verb == "help":
                print("Device commands:")
                print("  on [-b BRIGHTNESS] [-s SPEED] [--save]")
                print("  off [--save]")
                print("  brightness VALUE [--save]")
                print("  speed VALUE [--save]")
                print("  mode NAME [-s SPEED] [-b BRIGHT] [-d DIR] [--bg HEX] [COLORS...]")
                print("  length [VALUE]")
                print("  raw HEXBYTES")
                print("  scan")
                print()
                print("REPL commands:")
                print("  connect [ADDRESS]    connect to controller")
                print("  disconnect           disconnect from controller")
                print("  status               show connection status")
                print("  help                 show this help")
                print("  quit / exit          exit REPL")
                continue

            elif verb == "connect":
                if m.connected:
                    print(f"error: already connected to {addr}", file=sys.stderr)
                    continue
                if len(tokens) > 1:
                    target = tokens[1]
                else:
                    try:
                        devices = await McLovin.scan(timeout=globals_.timeout)
                        if not devices:
                            print("No controllers found.", file=sys.stderr)
                            continue
                        target = devices[0].address
                    except Exception as e:
                        print(f"error: {e}", file=sys.stderr)
                        continue
                try:
                    await m.connect(target, timeout=globals_.timeout)
                    addr = target
                    print(f"Connected to {addr}")
                except Exception as e:
                    print(f"error: {e}", file=sys.stderr)
                continue

            elif verb == "disconnect":
                if not m.connected:
                    print("error: not connected", file=sys.stderr)
                    continue
                try:
                    await m.disconnect()
                except Exception as e:
                    print(f"error: {e}", file=sys.stderr)
                addr = None
                continue

            # Device commands — route through existing machinery
            try:
                _, commands = split_argv(tokens)

                if not commands:
                    print(f"error: unknown command '{verb}'", file=sys.stderr)
                    continue

                # scan works without connection
                if any(name == "scan" for name, _ in commands):
                    devices = await McLovin.scan(timeout=globals_.timeout)
                    if not devices:
                        print("No controllers found.")
                    else:
                        for d in devices:
                            print(f"  {d.address}  {d.name}")
                    continue

                if not m.connected:
                    print("error: not connected (use 'connect' first)",
                          file=sys.stderr)
                    continue

                parsed_commands = []
                for cmd_name, cmd_argv in commands:
                    parser = COMMAND_PARSERS[cmd_name]()
                    cmd_args = parser.parse_args(cmd_argv)
                    parsed_commands.append((cmd_name, cmd_args))

                for cmd_name, cmd_args in parsed_commands:
                    await COMMAND_RUNNERS[cmd_name](m, cmd_args)

            except SystemExit:
                # argparse calls sys.exit on parse errors — swallow it
                pass
            except Exception as e:
                print(f"error: {e}", file=sys.stderr)

    finally:
        readline.write_history_file(HISTORY_FILE)
        if m.connected:
            await m.disconnect()


# --- Main ---


async def async_main():
    argv = sys.argv[1:]

    # Detect REPL mode before splitting commands
    repl_mode = "repl" in argv
    if repl_mode:
        argv = [a for a in argv if a != "repl"]

    global_argv, commands = split_argv(argv)

    global_parser = make_global_parser()

    if not commands and not repl_mode:
        global_parser.print_help()
        sys.exit(0)

    globals_ = global_parser.parse_args(global_argv)

    # Configure logging
    level = logging.DEBUG if globals_.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    if repl_mode:
        await async_repl(globals_)
        return

    # Parse each command's arguments
    parsed_commands = []
    for cmd_name, cmd_argv in commands:
        parser = COMMAND_PARSERS[cmd_name]()
        cmd_args = parser.parse_args(cmd_argv)
        parsed_commands.append((cmd_name, cmd_args))

    # Handle scan specially — no connection needed
    if any(name == "scan" for name, _ in parsed_commands):
        devices = await McLovin.scan(timeout=globals_.timeout)
        if not devices:
            print("No controllers found.")
        else:
            for d in devices:
                print(f"  {d.address}  {d.name}")
        return

    # Connect
    if globals_.address:
        address = globals_.address
    else:
        devices = await McLovin.scan(timeout=globals_.timeout)
        if not devices:
            print("No controllers found.", file=sys.stderr)
            sys.exit(1)
        address = devices[0].address

    m = McLovin()
    await m.connect(address, timeout=globals_.timeout)
    try:
        for cmd_name, cmd_args in parsed_commands:
            await COMMAND_RUNNERS[cmd_name](m, cmd_args)
    finally:
        await m.disconnect()


def main():
    try:
        asyncio.run(async_main())
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
