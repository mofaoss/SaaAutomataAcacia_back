# coding:utf-8
from typing import Any, Dict, List


CURRENT_DAILY_SEQUENCE_SCHEMA_VERSION = 2


def migrate_daily_sequence_schema(sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Migrate historical schedule payloads into current schema.
    v1 -> v2: rename `refresh_config` to `activation_config`.
    """
    migrated: List[Dict[str, Any]] = []
    for item in sequence or []:
        payload = dict(item)
        if "activation_config" not in payload and "refresh_config" in payload:
            payload["activation_config"] = payload.get("refresh_config")
        payload["schema_version"] = CURRENT_DAILY_SEQUENCE_SCHEMA_VERSION
        migrated.append(payload)
    return migrated

