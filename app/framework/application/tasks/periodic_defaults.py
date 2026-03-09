# coding:utf-8
import copy

from app.features.modules.periodic_task_manifest import PERIODIC_TASK_DEFAULT_SPECS


def build_default_periodic_task_sequence():
    sequence = []
    for spec in PERIODIC_TASK_DEFAULT_SPECS:
        sequence.append(
            {
                "id": spec["id"],
                "enabled": False,
                "use_periodic": False,
                "last_run": 0,
                "activation_config": copy.deepcopy(spec["activation_config"]),
                "execution_config": [],
            }
        )
    return sequence
