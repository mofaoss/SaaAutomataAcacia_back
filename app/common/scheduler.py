# -*- coding: utf-8 -*-
import copy
from datetime import datetime
from typing import List, Dict, Any

from PySide6.QtCore import QObject, QTimer, Signal

from app.common.config import config


class Scheduler(QObject):
    """
    Manages the scheduling, configuration, and triggering of all periodic tasks.
    """
    tasks_due = Signal(list)
    sequence_updated = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._task_sequence_cache = []
        self._init_and_normalize_sequence()

        # Core timer to check for due tasks every 30 seconds
        self.loop_timer = QTimer(self)
        self.loop_timer.timeout.connect(self.check_and_run_loop_tasks)

    def start(self):
        """Starts the main scheduling timer."""
        if not self.loop_timer.isActive():
            self.loop_timer.start(30000)  # 30 seconds

    def stop(self):
        """Stops the main scheduling timer."""
        self.loop_timer.stop()

    def _init_and_normalize_sequence(self):
        """Loads and normalizes the task sequence from config on initialization."""
        sequence = config.daily_task_sequence.value
        self._task_sequence_cache = self.normalize_task_sequence(sequence)
        self.save_task_sequence(self._task_sequence_cache, silent=True)

    def get_task_sequence(self) -> List[Dict[str, Any]]:
        """Returns the current task sequence."""
        return self._task_sequence_cache

    def save_task_sequence(self, sequence: List[Dict[str, Any]], silent: bool = False):
        """
        Saves the provided task sequence to the cache and the global config.
        """
        self._task_sequence_cache = sequence
        config.set(config.daily_task_sequence, copy.deepcopy(sequence))
        if not silent:
            self.sequence_updated.emit(self._task_sequence_cache)

    def is_rule_day_matched(self, rule: dict, now: datetime) -> bool:
        """Checks if the current day matches the execution rule."""
        exec_type = str(rule.get("type", "daily")).lower()

        if exec_type == "每周": exec_type = "weekly"
        elif exec_type == "每月": exec_type = "monthly"
        elif exec_type == "每天": exec_type = "daily"

        if exec_type == "weekly":
            return now.weekday() == int(rule.get("day", 0))
        elif exec_type == "monthly":
            return now.day == int(rule.get("day", 1))

        return True  # 'daily' matches every day

    def check_and_run_loop_tasks(self):
        """
        The core logic of the scheduler, executed periodically by the loop_timer.
        It checks for tasks that are due and emits the `tasks_due` signal.
        """
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        new_tasks_found = []
        sequence_updated = False

        sequence = self.get_task_sequence()
        for task_cfg in sequence:
            task_id = task_cfg.get("id")

            if not task_cfg.get("use_periodic"):
                continue

            exec_rules = task_cfg.get("execution_config", [])
            for rule in exec_rules:
                if rule.get("time") == current_time_str:
                    if self.is_rule_day_matched(rule, now):
                        rule_progress = task_cfg.get("rule_progress", {})
                        rule_key = f"{rule.get('type')}_{rule.get('day')}_{current_time_str}"
                        prog = rule_progress.get(rule_key, 0)
                        last_trigger_ts = prog.get("last_run", 0) if isinstance(prog, dict) else prog

                        # Prevent re-triggering within the same minute
                        if int(now.timestamp()) - int(last_trigger_ts) > 60:
                            max_runs = int(rule.get("max_runs", 1))
                            if max_runs > 0:
                                new_tasks_found.extend([task_id] * max_runs)

                            if isinstance(prog, dict):
                                prog["last_run"] = int(now.timestamp())
                                rule_progress[rule_key] = prog
                            else:
                                rule_progress[rule_key] = int(now.timestamp())

                            task_cfg["rule_progress"] = rule_progress
                            sequence_updated = True
                            break  # Move to the next task_cfg

        if sequence_updated:
            self.save_task_sequence(sequence)

        if new_tasks_found:
            self.tasks_due.emit(new_tasks_found)

    @staticmethod
    def normalize_task_sequence(sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalizes the task sequence, ensuring all default tasks are present,
        and setting proper default values for newly added tasks.
        """
        defaults = copy.deepcopy(config.daily_task_sequence.defaultValue)
        default_by_id = {item["id"]: item for item in defaults}
        normalized = []
        seen = set()

        for item in sequence or []:
            task_id = item.get("id")
            if task_id not in default_by_id:
                continue
            merged = copy.deepcopy(default_by_id[task_id])
            merged.update(item)

            # Standardize activation_config
            activation_rules = merged.get("activation_config")
            if activation_rules is None:
                activation_rules = merged.get("refresh_config", {}) or {}
            if isinstance(activation_rules, dict):
                activation_rules = [activation_rules]
            if not activation_rules:
                activation_rules = [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
            merged["activation_config"] = activation_rules
            merged.pop("refresh_config", None)

            # Standardize execution_config
            execution_rules = merged.get("execution_config")
            if execution_rules is None:
                execution_rules = []
            elif isinstance(execution_rules, dict):
                execution_rules = [execution_rules]
            merged["execution_config"] = execution_rules

            normalized.append(merged)
            seen.add(task_id)

        # Add any missing default tasks
        for item in defaults:
            if item["id"] not in seen:
                item["execution_config"] = []  # New tasks start with no execution rules
                if not item.get("activation_config"):
                    item["activation_config"] = [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
                normalized.append(copy.deepcopy(item))

        # Ensure 'task_login' is always first and enabled
        login_task = next((t for t in normalized if t["id"] == "task_login"), None)
        if login_task:
            normalized.remove(login_task)
            login_task["enabled"] = True
            normalized.insert(0, login_task)

        return normalized
