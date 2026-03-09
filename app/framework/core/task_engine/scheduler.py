# coding:utf-8
import copy
from datetime import datetime
from typing import Any, Dict, List

from PySide6.QtCore import QObject, QTimer, Signal

from app.framework.application.tasks.daily_policy import MANDATORY_DAILY_TASK_IDS, PRIMARY_TASK_ID
from app.framework.infra.config.app_config import config
from app.framework.core.config.daily_sequence import normalize_daily_task_sequence
from app.framework.core.config.migration import migrate_daily_sequence_schema


class Scheduler(QObject):
    """Manage periodic task triggering and sequence persistence."""

    tasks_due = Signal(list)
    sequence_updated = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._task_sequence_cache = []
        self._init_and_normalize_sequence()

        self.loop_timer = QTimer(self)
        self.loop_timer.timeout.connect(self.check_and_run_loop_tasks)

    def start(self):
        if not self.loop_timer.isActive():
            self.loop_timer.start(30000)

    def stop(self):
        self.loop_timer.stop()

    def _init_and_normalize_sequence(self):
        sequence = migrate_daily_sequence_schema(config.daily_task_sequence.value)
        defaults = copy.deepcopy(config.daily_task_sequence.defaultValue)
        self._task_sequence_cache = normalize_daily_task_sequence(
            sequence=sequence,
            defaults=defaults,
            mandatory_task_ids=MANDATORY_DAILY_TASK_IDS,
            primary_task_id=PRIMARY_TASK_ID,
        )
        self.save_task_sequence(self._task_sequence_cache, silent=True)

    def get_task_sequence(self) -> List[Dict[str, Any]]:
        return self._task_sequence_cache

    def save_task_sequence(self, sequence: List[Dict[str, Any]], silent: bool = False):
        self._task_sequence_cache = sequence
        config.set(config.daily_task_sequence, copy.deepcopy(sequence))
        if not silent:
            self.sequence_updated.emit(self._task_sequence_cache)

    def is_rule_day_matched(self, rule: dict, now: datetime) -> bool:
        exec_type = str(rule.get("type", "daily")).lower()
        if exec_type == "每周":
            exec_type = "weekly"
        elif exec_type == "每月":
            exec_type = "monthly"
        elif exec_type == "每天":
            exec_type = "daily"

        if exec_type == "weekly":
            return now.weekday() == int(rule.get("day", 0))
        if exec_type == "monthly":
            return now.day == int(rule.get("day", 1))
        return True

    def check_and_run_loop_tasks(self):
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        new_tasks_found = []
        sequence_updated = False

        sequence = self.get_task_sequence()
        for task_cfg in sequence:
            if not task_cfg.get("use_periodic"):
                continue

            exec_rules = task_cfg.get("execution_config", [])
            for rule in exec_rules:
                if rule.get("time") != current_time_str:
                    continue
                if not self.is_rule_day_matched(rule, now):
                    continue

                rule_progress = task_cfg.get("rule_progress", {})
                rule_key = f"{rule.get('type')}_{rule.get('day')}_{current_time_str}"
                prog = rule_progress.get(rule_key, 0)
                last_trigger_ts = prog.get("last_run", 0) if isinstance(prog, dict) else prog

                if int(now.timestamp()) - int(last_trigger_ts) <= 60:
                    continue

                max_runs = int(rule.get("max_runs", 1))
                if max_runs > 0:
                    new_tasks_found.extend([task_cfg.get("id")] * max_runs)

                if isinstance(prog, dict):
                    prog["last_run"] = int(now.timestamp())
                    rule_progress[rule_key] = prog
                else:
                    rule_progress[rule_key] = int(now.timestamp())

                task_cfg["rule_progress"] = rule_progress
                sequence_updated = True
                break

        if sequence_updated:
            self.save_task_sequence(sequence)

        if new_tasks_found:
            self.tasks_due.emit(new_tasks_found)

    @staticmethod
    def normalize_task_sequence(sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        defaults = copy.deepcopy(config.daily_task_sequence.defaultValue)
        return normalize_daily_task_sequence(
            sequence=sequence,
            defaults=defaults,
            mandatory_task_ids=MANDATORY_DAILY_TASK_IDS,
            primary_task_id=PRIMARY_TASK_ID,
        )

