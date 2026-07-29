#!/usr/bin/env python3
"""Demo script exercising the McLovin BLE control library.

Usage:
    python demo.py                     # scan for N8H-1AF, connect to first match
    python demo.py AA:BB:CC:DD:EE:FF   # connect by MAC address
"""

import asyncio
import logging
import sys

from mclovin import McLovin, MODE_CHASING, MODE_STATIC


async def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) > 1:
        address = sys.argv[1]
    else:
        devices = await McLovin.scan()
        if not devices:
            print("No controllers found.")
            sys.exit(1)
        for d in devices:
            print(f"  {d.address}  {d.name}")
        address = devices[0].address

    m = McLovin()
    await m.connect(address)

    try:
        # Turn on
        print("Turning on...")
        await m.on()
        await asyncio.sleep(1)

        # Solid red
        print("Red")
        await m.set_colors([(255, 0, 0)])
        await m.set_mode(MODE_STATIC, color_count=1)
        await asyncio.sleep(1)

        # Solid green
        print("Green")
        await m.set_colors([(0, 255, 0)])
        await m.set_mode(MODE_STATIC, color_count=1)
        await asyncio.sleep(1)

        # Solid blue
        print("Blue")
        await m.set_colors([(0, 0, 255)])
        await m.set_mode(MODE_STATIC, color_count=1)
        await asyncio.sleep(1)

        # Chasing mode with R/G/B
        print("Chasing R/G/B...")
        await m.set_colors([(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        await m.set_mode(MODE_CHASING, color_count=3, speed=50)
        await asyncio.sleep(3)

        # Brightness sweep: down then up
        print("Brightness sweep down...")
        for b in range(255, 1, -25):
            await m.set_brightness(b, save=False)
            await asyncio.sleep(0.15)

        print("Brightness sweep up...")
        for b in range(2, 256, 25):
            await m.set_brightness(min(b, 255), save=False)
            await asyncio.sleep(0.15)
        await m.set_brightness(255, save=True)

        await asyncio.sleep(0.5)

        # Turn off
        print("Turning off.")
        await m.off()

    finally:
        await m.disconnect()

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
