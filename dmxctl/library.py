"""Бібліотека моделей приладів: вбудовані (WASH 243) + зібрана база (tools/build_library.py)."""
from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path

from .fixtures import BUILTIN_MODELS

log = logging.getLogger(__name__)

TYPES = ["bar", "par", "head", "strobe", "matrix", "effect", "other"]
RECENT = "recent"          # розділ «Нещодавно використані»
RECENT_LIMIT = 24

MAKER_ALIASES = {"american dj": "adj", "chauvet": "chauvet dj", "stairville": "thomann", "eurolite": "steinigke",
                 "martin": "martin professional", "elation": "elation professional"}

_MODELS: list[dict] | None = None
_BY_KEY: dict[tuple[str, str], dict] | None = None


def models() -> list[dict]:
    global _MODELS
    if _MODELS is None:
        path = Path(__file__).parent / "library.json.gz"
        try:
            base = json.loads(gzip.decompress(path.read_bytes()))["fixtures"]
        except (OSError, ValueError, KeyError):
            log.exception("Не вдалося завантажити бібліотеку приладів")
            base = []
        _MODELS = [{**m, "builtin": True} for m in BUILTIN_MODELS] + base
    return _MODELS


def find(maker: str, name: str) -> dict | None:
    """Модель за виробником і назвою."""
    global _BY_KEY
    if _BY_KEY is None:
        _BY_KEY = {}
        for fx in models():
            _BY_KEY.setdefault((fx["m"], fx["n"]), fx)
    return _BY_KEY.get((maker, name))


def profile_name(fx: dict, mode: list) -> str:
    """Назва профілю режиму моделі (так само, як у інтерфейсі)."""
    if len(mode) > 2 and mode[2]:
        return mode[2]
    return f"{fx['m']} {fx['n']} · {mode[0]} ({len(mode[1])} кан.)"


def profile_owner(name: str, channels: list[str]) -> dict | None:
    """Модель і режим, яким належить профіль із такою назвою й каналами (для старих конфігурацій)."""
    for fx in models():
        for mode in fx["modes"]:
            if mode[1] == channels and profile_name(fx, mode) == name:
                return {"m": fx["m"], "n": fx["n"], "mode": mode[0]}
    return None


def _matches(fx: dict, words: list[str]) -> bool:
    text = f"{fx['m']} {MAKER_ALIASES.get(fx['m'].lower(), '')} {fx['n']}".lower()
    return all(w in text for w in words)


def _words(query: str) -> list[str]:
    return [w for w in query.lower().split() if w]


def _recent_models(recent: list[dict]) -> list[dict]:
    out = []
    for r in recent:
        fx = find(r.get("m", ""), r.get("n", ""))
        if fx is not None:
            out.append(fx)
    return out


def search(query: str, limit: int = 40, kind: str = "", offset: int = 0,
           recent: list[dict] | None = None) -> list[dict]:
    words = _words(query)
    if kind == RECENT:   # у порядку використання, найновіші першими
        hits = [fx for fx in _recent_models(recent or []) if _matches(fx, words)]
        return hits[offset:offset + limit]
    hits = [fx for fx in models() if (not kind or fx.get("t") == kind) and _matches(fx, words)]
    first = words[0] if words else ""
    hits.sort(key=lambda fx: (not fx.get("builtin"),
                              0 if first and (fx["m"].lower().startswith(first) or fx["n"].lower().startswith(first)) else 1,
                              fx["m"].lower(), fx["n"].lower()))
    return hits[offset:offset + limit]


def counts(query: str, recent: list[dict] | None = None) -> dict[str, int]:
    words = _words(query)
    out = {t: 0 for t in TYPES}
    for fx in models():
        if _matches(fx, words):
            out[fx.get("t", "other")] = out.get(fx.get("t", "other"), 0) + 1
    out[RECENT] = sum(1 for fx in _recent_models(recent or []) if _matches(fx, words))
    return out
