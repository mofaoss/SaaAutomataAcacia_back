# coding:utf-8
import logging
from typing import Optional

from app.core.observability.error_codes import AppErrorCode


def capture_exception(logger: logging.Logger, error: Exception, code: Optional[AppErrorCode] = None, context: str = ""):
    """Uniform exception reporting helper for application and core layers."""
    prefix = f"[{code.value}] " if code else ""
    suffix = f" | context={context}" if context else ""
    logger.error(f"{prefix}{error}{suffix}")

