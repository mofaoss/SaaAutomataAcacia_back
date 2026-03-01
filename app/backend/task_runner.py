import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class RunnerStatus:
    state: str = "idle"
    current_task: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    message: str = ""


class DailyTaskRunner:
    TASKS = [
        ("entry", "自动登录", "Auto Login"),
        ("collect", "领取物资", "Collect Supplies"),
        ("shop", "商店购买", "Shop"),
        ("stamina", "刷体力", "Use Stamina"),
        ("person", "人物碎片", "Character Shards"),
        ("chasm", "精神拟境", "Neural Simulation"),
        ("reward", "领取奖励", "Claim Rewards"),
    ]

    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.status = RunnerStatus()
        self._worker = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, selected: Optional[List[str]] = None) -> bool:
        with self._lock:
            if self.is_running():
                return False
            self._stop_event.clear()
            self.status = RunnerStatus(state="running", started_at=datetime.now().isoformat(timespec="seconds"))
            self._thread = threading.Thread(target=self._run, args=(selected,), daemon=True)
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
            data = {
                "state": self.status.state,
                "current_task": self.status.current_task,
                "started_at": self.status.started_at,
                "finished_at": self.status.finished_at,
                "message": self.status.message,
                "running": self.is_running(),
            }
        return data

    def _run(self, selected: Optional[List[str]] = None):
        from app.common.config import config, is_non_chinese_ui_language
        from app.common.logger import logger
        from app.modules.base_task.base_task import BaseTask
        from app.modules.chasm.chasm import ChasmModule
        from app.modules.collect_supplies.collect_supplies import CollectSuppliesModule
        from app.modules.enter_game.enter_game import EnterGameModule
        from app.modules.get_reward.get_reward import GetRewardModule
        from app.modules.ocr import ocr
        from app.modules.person.person import PersonModule
        from app.modules.shopping.shopping import ShoppingModule
        from app.modules.use_power.use_power import UsePowerModule

        class _Worker(BaseTask):
            def __init__(self):
                super().__init__()
                self._running = True

            def stop(self, reason=None):
                self._running = False
                if reason:
                    logger.warning(f"检测到中断，停止自动任务：{reason}")
                if self.auto is not None:
                    try:
                        self.auto.stop()
                    except Exception:
                        pass

        worker = _Worker()
        self._worker = worker

        task_map = {
            "entry": EnterGameModule,
            "collect": CollectSuppliesModule,
            "shop": ShoppingModule,
            "stamina": UsePowerModule,
            "person": PersonModule,
            "chasm": ChasmModule,
            "reward": GetRewardModule,
        }

        if not selected:
            selected = []
            option_map = {
                "entry": bool(config.get(config.CheckBox_entry_1)),
                "collect": bool(config.get(config.CheckBox_stamina_2)),
                "shop": bool(config.get(config.CheckBox_shop_3)),
                "stamina": bool(config.get(config.CheckBox_use_power_4)),
                "person": bool(config.get(config.CheckBox_person_5)),
                "chasm": bool(config.get(config.CheckBox_chasm_6)),
                "reward": bool(config.get(config.CheckBox_reward_7)),
            }
            selected = [k for k, v in option_map.items() if v]

        if not selected:
            with self._lock:
                self.status.state = "stopped"
                self.status.message = "no task selected"
                self.status.finished_at = datetime.now().isoformat(timespec="seconds")
            return

        try:
            for code, name_zh, name_en in self.TASKS:
                if code not in selected:
                    continue
                if self._stop_event.is_set() or not worker._running:
                    break

                with self._lock:
                    self.status.current_task = code

                task_name = name_en if is_non_chinese_ui_language() else name_zh
                logger.info(f"当前任务：{task_name}")

                if not worker.init_auto("game"):
                    with self._lock:
                        self.status.state = "error"
                        self.status.message = "failed to initialize automation"
                    return

                worker.auto.reset()
                module_cls = task_map[code]
                module_cls(worker.auto, logger).run()

                if self._stop_event.is_set() or not worker._running:
                    break

            with self._lock:
                if self._stop_event.is_set() or not worker._running:
                    self.status.state = "stopped"
                    if not self.status.message:
                        self.status.message = "stopped"
                else:
                    self.status.state = "finished"
                    self.status.message = "all selected tasks completed"
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
                self.status.current_task = None
                self.status.finished_at = datetime.now().isoformat(timespec="seconds")
            self._worker = None
