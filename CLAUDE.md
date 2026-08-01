# For Claude Code / AI assistants:

- **Project**: McLovin — BLE control library and CLI for Mictuning LED controllers
- **Goal**: Custom controller replacing the stock Mictuning Android app
- **Status**: Known protocol documented, library and CLI working

## Key Info

- Original APK package: `com.qunchen.headlightSpp`
- Uses BLE GATT (despite package name mentioning SPP)

## Source Layout

- `src/mclovin/lib.py` — BLE control library (`McLovin` class)
- `src/mclovin/cli.py` — CLI tool (`mcli` entry point)
- `src/mclovin/__init__.py` — re-exports public API from lib.py
- `scripts/demo.py` — example script
- `docs/protocol.md` — reverse-engineered protocol spec
- `docs/mclovin-spec.md` — library API spec
- `docs/mcli-spec.md` — CLI spec

## Notes

- Install with `pip install -e .` for development
- `mcli` console script is defined in pyproject.toml
