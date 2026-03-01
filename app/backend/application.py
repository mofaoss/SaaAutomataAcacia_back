from typing import Dict, Optional


class BackendApplication:
    def __init__(self, daily_runner, feature_runner, command_registry, log_hub):
        self.daily_runner = daily_runner
        self.feature_runner = feature_runner
        self.command_registry = command_registry
        self.log_hub = log_hub

    def health(self) -> Dict:
        return {"ok": True, "service": "saa-backend"}

    def list_commands(self) -> Dict:
        return {"ok": True, "commands": self.command_registry.list_commands()}

    def status(self) -> Dict:
        return self.daily_runner.snapshot()

    def logs(self, limit: int = 200) -> Dict:
        return {"logs": self.log_hub.history(limit=limit)}

    def execute(self, command_name: str, payload: Optional[Dict] = None) -> Dict:
        return self.command_registry.execute(command_name, payload=payload or {})

    def shutdown(self, reason: str = "server shutting down"):
        try:
            self.daily_runner.stop(reason=reason)
        except Exception:
            pass
        try:
            self.feature_runner.stop(reason=reason)
        except Exception:
            pass