# coding:utf-8

from app.framework.application.tasks.daily_policy import PRIMARY_TASK_ID


PERIODIC_TASK_DEFAULT_SPECS = [
    {"id": PRIMARY_TASK_ID, "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]},
    {"id": "task_supplies", "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]},
    {"id": "task_shop", "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]},
    {"id": "task_stamina", "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]},
    {"id": "task_shards", "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]},
    {"id": "task_chasm", "activation_config": [{"type": "weekly", "day": 1, "time": "10:00", "max_runs": 1}]},
    {"id": "task_operation", "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]},
    {"id": "task_reward", "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]},
    {"id": "task_weapon", "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]},
    {"id": "task_shard_exchange", "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]},
    {"id": "task_close_game", "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]},
]
