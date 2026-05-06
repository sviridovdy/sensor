import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

import aiohttp
import yaml

from automations import AutomationRunner
from presence import PresenceTracker
from scanner import scan_devices

_log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        logger.error(
            f"Config file '{path}' not found. "
            "Copy config.example.yaml to config.yaml and edit it."
        )
        sys.exit(1)
    with p.open() as f:
        return yaml.safe_load(f)


async def run(config: dict):
    bt = config.get("bluetooth", {})
    scan_interval: int = bt.get("scan_interval", 30)
    scan_duration: float = bt.get("scan_duration", 8)
    miss_threshold: int = bt.get("miss_threshold", 3)

    devices: list[dict] = config.get("devices", [])
    if not devices:
        logger.warning("No devices configured — nothing to track.")
        return

    tracker = PresenceTracker(devices, miss_threshold=miss_threshold)
    runner = AutomationRunner(config.get("automations", []), devices)

    names = [d["name"] for d in devices]
    logger.info(f"Watching {len(devices)} device(s): {names}")
    logger.info(
        f"Scan every {scan_interval}s "
        f"(active for {scan_duration}s, away after {miss_threshold} misses)"
    )

    stop_event = asyncio.Event()

    # add_signal_handler is Unix-only; on Windows Ctrl-C raises KeyboardInterrupt
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
    except NotImplementedError:
        pass

    try:
        async with aiohttp.ClientSession() as session:
            while not stop_event.is_set():
                try:
                    seen = await scan_devices(devices, scan_duration)
                    events = tracker.update(seen)
                    for event in events:
                        await runner.handle_event(event, session)
                except Exception:
                    logger.exception("Unhandled error in scan cycle")

                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=scan_interval)
                except asyncio.TimeoutError:
                    pass
    except KeyboardInterrupt:
        pass

    logger.info("Sensor stopped.")


def main():
    config = load_config()
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
