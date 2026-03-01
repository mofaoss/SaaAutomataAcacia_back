from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class CommandSpec:
    name: str
    description: str
    payload_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]


class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, CommandSpec] = {}

    def register(self, name: str, description: str, payload_schema: Optional[Dict[str, Any]],
                 handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self._commands[name] = CommandSpec(
            name=name,
            description=description,
            payload_schema=payload_schema or {},
            handler=handler,
        )

    def execute(self, name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if name not in self._commands:
            return {"ok": False, "error": f"unknown command: {name}", "code": "unknown_command"}
        payload = payload or {}
        return self._commands[name].handler(payload)

    def list_commands(self):
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "payload_schema": spec.payload_schema,
            }
            for spec in sorted(self._commands.values(), key=lambda x: x.name)
        ]


def _open_game_directly() -> Dict[str, Any]:
    from app.common.logger import logger
    from app.common.utils import launch_game_with_guard

    result = launch_game_with_guard(logger=logger)
    if "process" in result:
        result.pop("process", None)
    return result


def build_default_registry(daily_runner, feature_runner):
    registry = CommandRegistry()

    def _daily_start(payload):
        tasks = payload.get("tasks") if isinstance(payload, dict) else None
        if tasks is not None and not isinstance(tasks, list):
            return {"ok": False, "error": "tasks must be a list", "code": "invalid_payload"}
        if feature_runner.is_running():
            return {"ok": False, "error": "feature runner is running", "code": "runner_busy"}
        accepted = daily_runner.start(tasks)
        if not accepted:
            return {"ok": False, "error": "daily runner is already running", "code": "runner_busy"}
        return {"ok": True, "status": daily_runner.snapshot()}

    def _daily_stop(payload):
        reason = str(payload.get("reason", "user requested"))
        accepted = daily_runner.stop(reason=reason)
        if not accepted:
            return {"ok": False, "error": "daily runner is not running", "code": "runner_not_running"}
        return {"ok": True, "status": daily_runner.snapshot()}

    def _daily_status(_payload):
        return {"ok": True, "status": daily_runner.snapshot()}

    def _feature_start(payload):
        feature = payload.get("feature")
        if not feature or not isinstance(feature, str):
            return {"ok": False, "error": "feature is required", "code": "invalid_payload"}
        if daily_runner.is_running():
            return {"ok": False, "error": "daily runner is running", "code": "runner_busy"}
        accepted = feature_runner.start(feature)
        if not accepted:
            return {"ok": False, "error": "feature runner is already running", "code": "runner_busy"}
        return {"ok": True, "status": feature_runner.snapshot()}

    def _feature_stop(payload):
        reason = str(payload.get("reason", "user requested"))
        accepted = feature_runner.stop(reason=reason)
        if not accepted:
            return {"ok": False, "error": "feature runner is not running", "code": "runner_not_running"}
        return {"ok": True, "status": feature_runner.snapshot()}

    def _feature_status(_payload):
        return {
            "ok": True,
            "status": feature_runner.snapshot(),
            "supported_features": feature_runner.supported_features(),
        }

    def _game_open(_payload):
        return _open_game_directly()

    registry.register(
        name="game.open",
        description="Open game executable based on config",
        payload_schema={},
        handler=_game_open,
    )
    registry.register(
        name="daily.start",
        description="Start daily tasks",
        payload_schema={"tasks": ["entry", "collect", "shop", "stamina", "person", "chasm", "reward"]},
        handler=_daily_start,
    )
    registry.register(
        name="daily.stop",
        description="Stop daily tasks",
        payload_schema={"reason": "string"},
        handler=_daily_stop,
    )
    registry.register(
        name="daily.status",
        description="Get daily runner status",
        payload_schema={},
        handler=_daily_status,
    )
    registry.register(
        name="feature.start",
        description="Start one feature module",
        payload_schema={"feature": "string"},
        handler=_feature_start,
    )
    registry.register(
        name="feature.stop",
        description="Stop running feature module",
        payload_schema={"reason": "string"},
        handler=_feature_stop,
    )
    registry.register(
        name="feature.status",
        description="Get feature runner status",
        payload_schema={},
        handler=_feature_status,
    )

    return registry
