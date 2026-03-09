# coding:utf-8
import json

from qfluentwidgets import ConfigSerializer


class TaskSequenceSerializer(ConfigSerializer):
    """Serializer for complex task sequence structures in config persistence."""

    def serialize(self, sequence):
        return json.dumps(sequence, ensure_ascii=False)

    def deserialize(self, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                pass
        elif isinstance(value, list):
            return value
        return []

