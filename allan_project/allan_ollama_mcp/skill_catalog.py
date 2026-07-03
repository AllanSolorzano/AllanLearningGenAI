"""Optional skill summaries for intent discovery and planning (ALLAN_SKILLS_DIRS / ALLAN_SKILLS_DIR)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


def _paths_from_env() -> list[Path]:
    raw = (os.environ.get("ALLAN_SKILLS_DIRS") or "").strip()
    if not raw:
        raw = (os.environ.get("ALLAN_SKILLS_DIR") or "").strip()
    if not raw:
        return []
    return [Path(p.strip()).expanduser().resolve() for p in raw.split(",") if p.strip()]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines()[:48]:
        s = line.strip()
        if s.startswith("#"):
            t = re.sub(r"^#+\s*", "", s).strip()
            if t:
                return t[:160]
    return fallback[:160]


def _summary_after_frontmatter(text: str, max_chars: int) -> str:
    body = text
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            body = body[end + 4 :].lstrip()
    body = body.strip()
    if not body:
        return ""
    para = []
    for block in body.split("\n\n"):
        b = block.strip().replace("\n", " ")
        if b:
            para.append(b)
            break
    s = para[0] if para else body.replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_chars:
        return s[: max_chars - 1] + "…"
    return s


def load_available_skills(*, max_skills: int = 20, max_summary_chars: int = 200) -> list[dict[str, Any]]:
    """Return compact skill rows for LLM prompts; empty if env paths unset or missing."""
    roots = _paths_from_env()
    if not roots:
        return []

    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    for root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.suffix.lower() == ".md":
            paths = [root]
        elif root.is_dir():
            paths = sorted(root.rglob("SKILL.md"))
        else:
            continue

        for path in paths:
            if len(out) >= max_skills:
                return out
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            text = _read_text(path)
            skill_id = path.parent.name if path.name.upper() == "SKILL.MD" else path.stem
            title = _title_from_markdown(text, skill_id)
            summary = _summary_after_frontmatter(text, max_summary_chars)
            try:
                rel = str(path.relative_to(root if root.is_dir() else path.parent))
            except ValueError:
                rel = path.name
            out.append(
                {
                    "id": skill_id,
                    "path": rel,
                    "title": title,
                    "summary": summary,
                }
            )

    return out
