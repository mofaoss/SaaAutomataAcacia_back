# coding:utf-8
from __future__ import annotations


def build_initial_interface_keys(startup_target_index: int, auto_start_task: bool) -> list[str]:
    idx_map = {
        0: "display",
        1: "home",
        2: "additional",
    }
    ordered = [idx_map.get(int(startup_target_index), "display")]
    if auto_start_task:
        ordered.append("home")

    unique: list[str] = []
    seen: set[str] = set()
    for key in ordered:
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)
    return unique


def build_deferred_interface_keys() -> list[str]:
    return ["display", "home", "additional", "table", "help", "setting"]

