import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class FeatureRunnerStatus:
    state: str = "idle"
    feature: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    message: str = ""


class FeatureTaskRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._worker = None
        self.status = FeatureRunnerStatus()

    @staticmethod
    def _feature_map() -> Dict[str, tuple]:
        from app.modules.alien_guardian.alien_guardian import AlienGuardianModule
        from app.modules.capture_pals.capture_pals import CapturePalsModule
        from app.modules.drink.drink import DrinkModule
        from app.modules.fishing.fishing import FishingModule
        from app.modules.jigsaw.jigsaw import JigsawModule
        from app.modules.massaging.massaging import MassagingModule
        from app.modules.maze.maze import MazeModule
        from app.modules.operation_action.operation_action import OperationModule
        from app.modules.trigger.auto_f import AutoFModule
        from app.modules.trigger.nita_auto_e import NitaAutoEModule
        from app.modules.water_bomb.water_bomb import WaterBombModule

        return {
            "fishing": ("自动钓鱼", "Auto Fishing", FishingModule),
            "operation": ("周常行动", "Weekly Operation", OperationModule),
            "jigsaw": ("信源解析", "Jigsaw", JigsawModule),
            "water_bomb": ("心动水弹", "Water Bomb", WaterBombModule),
            "alien_guardian": ("异星守护", "Alien Guardian", AlienGuardianModule),
            "maze": ("迷宫", "Maze", MazeModule),
            "massaging": ("按摩", "Massaging", MassagingModule),
            "drink": ("喝酒", "Drink", DrinkModule),
            "capture_pals": ("抓帕鲁", "Capture Pals", CapturePalsModule),
            "auto_f": ("自动采集F", "Auto F", AutoFModule),
            "nita_auto_e": ("妮塔E自动QTE", "Nita Auto E", NitaAutoEModule),
        }

    def supported_features(self):
        return sorted(self._feature_map().keys())

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, feature: str) -> bool:
        with self._lock:
            if self.is_running():
                return False
            self._stop_event.clear()
            self.status = FeatureRunnerStatus(
                state="running",
                feature=feature,
                started_at=datetime.now().isoformat(timespec="seconds"),
            )
            self._thread = threading.Thread(target=self._run, args=(feature,), daemon=True)
            self._thread.start()
            return True

    def stop(self, reason: str = "user requested") -> bool:
        with self._lock:
            if not self.is_running():
                return False
            self._stop_event.set()
            if self._worker is not None:
                try:
                    self._worker.stop(reason=reason)
                except Exception:
                    pass
            self.status.message = reason
            return True

    def snapshot(self) -> Dict:
        with self._lock:
            return {
                "state": self.status.state,
                "feature": self.status.feature,
                "started_at": self.status.started_at,
                "finished_at": self.status.finished_at,
                "message": self.status.message,
                "running": self.is_running(),
            }

    def _run(self, feature: str):
        from app.common.config import is_non_chinese_ui_language
        from app.common.logger import logger
        from app.modules.base_task.base_task import BaseTask
        from app.modules.ocr import ocr

        features = self._feature_map()
        if feature not in features:
            with self._lock:
                self.status.state = "error"
                self.status.message = f"unsupported feature: {feature}"
                self.status.finished_at = datetime.now().isoformat(timespec="seconds")
            return

        name_zh, name_en, module_cls = features[feature]

        class _Worker(BaseTask):
            def __init__(self):
                super().__init__()
                self._running = True

            def stop(self, reason=None):
                self._running = False
                if reason:
                    logger.warning(f"检测到中断，停止功能任务：{reason}")
                if self.auto is not None:
                    try:
                        self.auto.stop()
                    except Exception:
                        pass

        worker = _Worker()
        self._worker = worker

        try:
            display_name = name_en if is_non_chinese_ui_language() else name_zh
            logger.info(f"当前功能：{display_name}")

            if not worker.init_auto("game"):
                with self._lock:
                    self.status.state = "error"
                    self.status.message = "failed to initialize automation"
                return

            worker.auto.reset()
            module_cls(worker.auto, logger).run()

            with self._lock:
                if self._stop_event.is_set() or not worker._running:
                    self.status.state = "stopped"
                    if not self.status.message:
                        self.status.message = "stopped"
                else:
                    self.status.state = "finished"
                    self.status.message = "feature completed"
        except Exception as e:
            with self._lock:
                self.status.state = "error"
                self.status.message = str(e)
        finally:
            try:
                ocr.stop_ocr()
            except Exception:
                pass
            if worker.auto is not None:
                try:
                    worker.auto.stop()
                except Exception:
                    pass
            with self._lock:
                self.status.finished_at = datetime.now().isoformat(timespec="seconds")
            self._worker = None
