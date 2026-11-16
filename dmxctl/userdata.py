"""Вибіркове видалення даних користувача з config.json (для вікна видалення програми).

python -m dmxctl.userdata --config <шлях> scenes fixtures ...

Частини: scenes — сцени; fixtures — прилади (разом із профілями їхніх моделей і нещодавніми моделями);
profiles — власні профілі каналів; colors — статичні кольори; settings — DMX-інтерфейс, яскравість і гарячі клавіші.
Якщо після видалення нічого не лишилося, config.json видаляється повністю.
Код виходу: 0 — готово, 2 — неправильні аргументи, 1 — помилка.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PARTS = ("scenes", "fixtures", "profiles", "colors", "settings")


def strip(cfg: dict, parts: set[str]) -> dict:
    """Повертає копію налаштувань без вибраних частин."""
    cfg = dict(cfg)
    profiles = dict(cfg.get("profiles") or {})
    device = set(cfg.get("device_profiles") or [])
    if "scenes" in parts:
        cfg.pop("scenes", None)
    if "fixtures" in parts:
        for k in ("fixtures", "recent_models", "device_profiles"):
            cfg.pop(k, None)
        profiles = {k: v for k, v in profiles.items() if k not in device}
    if "profiles" in parts:
        profiles = {k: v for k, v in profiles.items() if k in device}
    if "colors" in parts:
        cfg.pop("static_colors", None)
    if "settings" in parts:
        cfg.pop("output", None)
        cfg.pop("master", None)
        cfg.pop("hotkeys", None)
    if "profiles" in cfg or profiles:
        cfg["profiles"] = profiles
    return cfg


def _empty(cfg: dict) -> bool:
    return not any(v for k, v in cfg.items() if k not in ("device_profiles",))


def apply(path: Path, parts: set[str]) -> bool:
    """Видаляє частини з файлу налаштувань. True — файл видалено повністю."""
    if not path.exists():
        return True
    if set(PARTS) <= parts:
        path.unlink()
        return True
    cfg = strip(json.loads(path.read_text("utf-8")), parts)
    if _empty(cfg):
        path.unlink()
        return True
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(path)
    return False


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m dmxctl.userdata", description=__doc__.splitlines()[0])
    p.add_argument("--config", required=True, help="шлях до config.json")
    p.add_argument("parts", nargs="+", choices=PARTS)
    args = p.parse_args(argv)
    try:
        removed = apply(Path(args.config), set(args.parts))
    except (OSError, ValueError) as e:
        print(f"Помилка: {e}", file=sys.stderr)
        return 1
    print("removed" if removed else "kept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
