import logging
import aiohttp
from presence import PresenceEvent

logger = logging.getLogger(__name__)


class AutomationRunner:
    def __init__(self, automations: list[dict], devices: list[dict]):
        self._automations = automations

    async def handle_event(self, event: PresenceEvent, session: aiohttp.ClientSession):
        for automation in self._automations:
            trigger = automation.get("trigger", {})
            ttype = trigger.get("type")

            if ttype == "anyone_home" and event.type == "aggregate":
                actions = automation.get("on_arrive" if event.arrived else "on_leave", [])
                await self._run_actions(automation["name"], actions, event, session)

            elif ttype == "device" and event.type == "device":
                if trigger.get("device") == event.device_name:
                    actions = automation.get("on_arrive" if event.arrived else "on_leave", [])
                    await self._run_actions(automation["name"], actions, event, session)

    async def _run_actions(
        self,
        automation_name: str,
        actions: list[dict],
        event: PresenceEvent,
        session: aiohttp.ClientSession,
    ):
        if not actions:
            return
        logger.info(f"Running automation '{automation_name}' ({len(actions)} action(s))")
        for action in actions:
            await self._run_action(action, event, session)

    async def _run_action(
        self,
        action: dict,
        event: PresenceEvent,
        session: aiohttp.ClientSession,
    ):
        ctx = {
            "device_name": event.device_name,
            "device_mac": event.device_mac or "",
            "state": "home" if event.arrived else "away",
        }

        url = _render(action["url"], ctx)
        method = action.get("method", "POST").upper()
        headers = {k: _render(v, ctx) for k, v in action.get("headers", {}).items()}

        kwargs: dict = {"headers": headers}
        if "json" in action:
            kwargs["json"] = _render_deep(action["json"], ctx)
        elif "body" in action:
            kwargs["data"] = _render(str(action["body"]), ctx)

        try:
            async with session.request(method, url, **kwargs) as resp:
                logger.info(f"  {method} {url} -> {resp.status}")
                if resp.status >= 400:
                    body = await resp.text()
                    logger.warning(f"  Response body: {body[:300]}")
        except aiohttp.ClientError as exc:
            logger.error(f"  HTTP error calling {url}: {exc}")


def _render(template: str, ctx: dict) -> str:
    return template.format_map(ctx)


def _render_deep(obj, ctx: dict):
    """Recursively apply template substitution to strings inside dicts/lists."""
    if isinstance(obj, str):
        return _render(obj, ctx)
    if isinstance(obj, dict):
        return {k: _render_deep(v, ctx) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_render_deep(v, ctx) for v in obj]
    return obj  # int, float, bool, None — pass through unchanged
