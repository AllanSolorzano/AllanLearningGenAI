"""Application logging for allan_project (console + optional rotating file).

Environment:

  ALLAN_LOG_LEVEL          DEBUG, INFO, WARNING, ERROR (default: INFO)
  ALLAN_LOG_FILE           Override log file path (default: <project>/data/logs/allan_project.log)
  ALLAN_LOG_DIR            Directory when using default filename (default: <project>/data/logs)
  ALLAN_DISABLE_FILE_LOG   If 1/true, log only to stderr (no file)
  ALLAN_LOG_MAX_BYTES      Rotating file size cap (default: 2097152 = 2 MiB)
  ALLAN_LOG_BACKUP_COUNT   Rotating backup files kept (default: 3)

HTTP (local dev): ``GET /logs/tail?lines=200`` returns recent lines from the log file when file logging is enabled.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "allan_ollama_mcp"
_log_file_resolved: Path | None = None


def get_log_file_path() -> Path | None:
    """Absolute path to the rotating log file, or None if file logging is disabled."""
    return _log_file_resolved


def tail_lines(path: Path, max_lines: int) -> list[str]:
    """Return up to ``max_lines`` tail lines (best-effort for large files)."""
    if not path.is_file() or max_lines < 1:
        return []
    max_bytes = 512 * 1024
    with path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        if size == 0:
            return []
        read_size = min(size, max_bytes)
        f.seek(size - read_size)
        chunk = f.read()
    text = chunk.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return lines[-max_lines:] if len(lines) > max_lines else lines


def configure_logging() -> None:
    """Attach handlers to the ``allan_ollama_mcp`` logger (idempotent)."""
    global _log_file_resolved
    log = logging.getLogger(_LOGGER_NAME)
    if log.handlers:
        return

    level_name = os.environ.get("ALLAN_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)

    disable_file = os.environ.get("ALLAN_DISABLE_FILE_LOG", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if not disable_file:
        project_root = Path(__file__).resolve().parent.parent
        log_dir = Path(os.environ.get("ALLAN_LOG_DIR", project_root / "data" / "logs"))
        log_file = Path(os.environ.get("ALLAN_LOG_FILE", log_dir / "allan_project.log"))
        log_dir.mkdir(parents=True, exist_ok=True)
        max_bytes = int(os.environ.get("ALLAN_LOG_MAX_BYTES", str(2 * 1024 * 1024)))
        backup = int(os.environ.get("ALLAN_LOG_BACKUP_COUNT", "3"))
        fh = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        log.addHandler(fh)
        _log_file_resolved = log_file.resolve()
    else:
        _log_file_resolved = None

    log.propagate = False
