import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PresenceEvent:
    type: str              # "device" or "aggregate"
    device_name: str
    device_mac: Optional[str]
    arrived: bool          # True = arrived/home, False = left/away


class PresenceTracker:
    def __init__(self, devices: list[dict], miss_threshold: int = 3):
        self.miss_threshold = miss_threshold
        self._states: dict[str, dict] = {
            d["mac"].upper(): {
                "name": d["name"],
                "mac": d["mac"].upper(),
                "present": False,
                "miss_count": 0,
            }
            for d in devices
        }
        self._anyone_home = False

    @property
    def anyone_home(self) -> bool:
        return any(s["present"] for s in self._states.values())

    def update(self, seen_macs: set[str]) -> list[PresenceEvent]:
        """Process one scan result. Returns state-change events."""
        events: list[PresenceEvent] = []
        prev_anyone = self._anyone_home

        for mac, state in self._states.items():
            if mac in seen_macs:
                state["miss_count"] = 0
                if not state["present"]:
                    state["present"] = True
                    logger.info(f"{state['name']} arrived")
                    events.append(PresenceEvent(
                        type="device",
                        device_name=state["name"],
                        device_mac=mac,
                        arrived=True,
                    ))
            else:
                state["miss_count"] += 1
                if state["present"] and state["miss_count"] >= self.miss_threshold:
                    state["present"] = False
                    logger.info(
                        f"{state['name']} left "
                        f"(missed {self.miss_threshold} consecutive scans)"
                    )
                    events.append(PresenceEvent(
                        type="device",
                        device_name=state["name"],
                        device_mac=mac,
                        arrived=False,
                    ))

        curr_anyone = self.anyone_home
        if curr_anyone != prev_anyone:
            self._anyone_home = curr_anyone
            label = "someone home" if curr_anyone else "nobody home"
            logger.info(f"Aggregate state: {label}")
            events.append(PresenceEvent(
                type="aggregate",
                device_name="__anyone__",
                device_mac=None,
                arrived=curr_anyone,
            ))

        return events

    def status(self) -> dict:
        """Return current presence state for all devices (for logging/debugging)."""
        return {
            s["name"]: {
                "present": s["present"],
                "miss_count": s["miss_count"],
            }
            for s in self._states.values()
        }
