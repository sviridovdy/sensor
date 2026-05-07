import asyncio
import subprocess
import logging

logger = logging.getLogger(__name__)


def _hcitool_name(mac: str, timeout: int = 5) -> bool:
    """Classic BT name lookup. Works for paired phones regardless of lock state."""
    try:
        result = subprocess.run(
            ["hcitool", "name", mac],
            capture_output=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except FileNotFoundError:
        logger.error("hcitool not found — install bluez")
        return False
    except subprocess.TimeoutExpired:
        return False


async def scan_devices(devices: list[dict]) -> set[str]:
    """Returns the set of device MACs (uppercase) currently within range."""
    loop = asyncio.get_running_loop()
    present: set[str] = set()

    for device in devices:
        mac = device["mac"].upper()
        label = device["name"]

        found = await loop.run_in_executor(None, _hcitool_name, mac)
        if found:
            present.add(mac)
            logger.info(f"{label}: present")
        else:
            logger.info(f"{label}: not seen")

    return present
