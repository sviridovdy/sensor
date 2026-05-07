import asyncio
import subprocess
import logging
from bleak import BleakScanner

logger = logging.getLogger(__name__)


async def _ble_scan(duration: float) -> tuple[set[str], dict[str, str]]:
    """
    Passive BLE scan.
    Returns (set of MACs, dict mapping advertised-name -> MAC) — both uppercased.
    """
    discovered = await BleakScanner.discover(timeout=duration, return_adv=True)
    macs = {addr.upper() for addr in discovered}
    names = {d.name: addr.upper() for addr, (d, _) in discovered.items() if d.name}
    logger.info(f"BLE scan: {len(macs)} device(s), {len(names)} with names")
    for addr, (d, adv) in discovered.items():
        logger.info(f"  {addr.upper()}  name={d.name!r}  rssi={adv.rssi}")
    return macs, names


def _l2ping(mac: str, timeout: int = 5) -> bool:
    """L2CAP ping over classic BT. Can be blocked by Android when screen is off."""
    try:
        result = subprocess.run(
            ["l2ping", "-c", "1", "-t", str(timeout), mac],
            capture_output=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0
    except FileNotFoundError:
        logger.debug("l2ping not found; skipping")
        return False
    except subprocess.TimeoutExpired:
        return False


def _hcitool_name(mac: str, timeout: int = 5) -> bool:
    """
    Classic BT name lookup. More reliable than l2ping on Android —
    the phone responds even when locked as long as it's in range.
    """
    try:
        result = subprocess.run(
            ["hcitool", "name", mac],
            capture_output=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except FileNotFoundError:
        logger.debug("hcitool not found; skipping")
        return False
    except subprocess.TimeoutExpired:
        return False


async def scan_devices(devices: list[dict], scan_duration: float) -> set[str]:
    """
    Returns the set of device MACs (uppercase) currently within range.

    Detection order per device:
    1. BLE MAC match     — works for bonded devices with stable/resolved address
    2. BLE name match    — catches Android with randomized BLE MAC (set ble_name
                           in config to the name shown in BLE advertisements,
                           e.g. the phone's device name from Settings)
    3. hcitool name      — classic BT lookup; reliable for Pixel when screen off
    4. l2ping            — classic BT ping; fallback, often blocked when locked
    """
    ble_macs, ble_names = await _ble_scan(scan_duration)
    loop = asyncio.get_running_loop()
    present: set[str] = set()

    for device in devices:
        mac = device["mac"].upper()
        label = device["name"]

        if mac in ble_macs:
            present.add(mac)
            logger.info(f"{label}: found via BLE MAC")
            continue

        ble_name = device.get("ble_name") or device["name"]
        if ble_name in ble_names:
            present.add(mac)
            logger.info(f"{label}: found via BLE name '{ble_name}'")
            continue

        logger.info(f"{label}: not in BLE scan, trying classic BT")

        found = await loop.run_in_executor(None, _hcitool_name, mac)
        if found:
            present.add(mac)
            logger.info(f"{label}: found via hcitool name lookup")
            continue

        found = await loop.run_in_executor(None, _l2ping, mac)
        if found:
            present.add(mac)
            logger.info(f"{label}: found via l2ping")
            continue

        logger.info(f"{label}: not seen")

    return present
