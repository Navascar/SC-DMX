"""Перевірка та встановлення оновлень із GitHub Releases.

Оновлення встановлюється на місці: нові файли копіюються поверх теки застосунку,
config.json, віртуальне середовище та журнали не чіпаються. Після цього сервер
завершується з кодом RESTART_CODE, і лаунчер (dmxctl/__main__.py) запускає його знову.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from . import GITHUB_REPO, __version__

log = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent
RESTART_CODE = 42
API_URL = os.environ.get("SC_DMX_UPDATE_API", f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest")
ASSET_NAME = "SC-DMX.zip"
# Що зберігається між версіями
KEEP = {"config.json", "config.tmp", ".venv", "venv", ".git", "sc-dmx.log", ".update-backup", "Uninstall.exe"}


def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(latest: str, current: str = __version__) -> bool:
    return parse_version(latest) > parse_version(current)


def _open(url: str, timeout: float = 15):
    req = urllib.request.Request(url, headers={
        "User-Agent": "SC-DMX-updater",
        "Accept": "application/vnd.github+json" if "api.github.com" in url else "*/*",
    })
    return urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context())


def check() -> dict:
    """Повертає {current, latest, available, notes, url, page}."""
    with _open(API_URL) as resp:
        rel = json.load(resp)
    latest = rel.get("tag_name", "").lstrip("vV")
    url = next((a["browser_download_url"] for a in rel.get("assets", []) if a.get("name") == ASSET_NAME),
               rel.get("zipball_url"))
    return {
        "current": __version__,
        "latest": latest,
        "available": bool(latest) and is_newer(latest) and bool(url),
        "notes": (rel.get("body") or "").strip()[:4000],
        "url": url,
        "page": rel.get("html_url", f"https://github.com/{GITHUB_REPO}/releases"),
    }


def can_self_update() -> str | None:
    """None — можна оновлюватись; інакше пояснення, чому ні."""
    if (APP_DIR / ".git").exists():
        return "це робоча копія git — оновлюйте командою git pull"
    if not os.access(APP_DIR, os.W_OK):
        return f"немає прав на запис у {APP_DIR}"
    return None


def _find_root(extracted: Path) -> Path:
    """Тека всередині архіву, де лежить пакет dmxctl (zipball має вкладену теку)."""
    for cand in [extracted, *sorted(p for p in extracted.iterdir() if p.is_dir())]:
        if (cand / "dmxctl" / "__init__.py").exists():
            return cand
    raise RuntimeError("в архіві оновлення немає теки dmxctl")


def install_from_zip(zip_path: Path, app_dir: Path = APP_DIR) -> None:
    """Розпаковує архів і замінює файли застосунку з резервною копією та відкатом."""
    with tempfile.TemporaryDirectory(prefix="sc-dmx-") as tmp:
        tmp = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            root = tmp.resolve()
            for name in zf.namelist():  # захист від шляхів на кшталт ../../ (zip-slip)
                target = (tmp / name).resolve()
                if target != root and not target.is_relative_to(root):
                    raise RuntimeError(f"небезпечний шлях в архіві: {name}")
            zf.extractall(tmp)
        src = _find_root(tmp)

        backup = app_dir / ".update-backup"
        shutil.rmtree(backup, ignore_errors=True)
        backup.mkdir()
        moved: list[Path] = []
        try:
            for item in list(app_dir.iterdir()):
                if item.name in KEEP:
                    continue
                shutil.move(str(item), backup / item.name)
                moved.append(item)
            for item in src.iterdir():
                if item.name in KEEP:
                    continue
                dest = app_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
        except Exception:
            log.exception("Помилка встановлення — відкат")
            restore_backup(app_dir)
            raise
        finally:
            if not any(backup.iterdir()):
                backup.rmdir()


def restore_backup(app_dir: Path = APP_DIR) -> None:
    """Повертає файли попередньої версії з .update-backup (усе, крім KEEP)."""
    backup = app_dir / ".update-backup"
    if not backup.is_dir() or not any(backup.iterdir()):
        return
    for item in list(app_dir.iterdir()):
        if item.name not in KEEP:
            shutil.rmtree(item, ignore_errors=True) if item.is_dir() else item.unlink(missing_ok=True)
    for item in list(backup.iterdir()):
        shutil.move(str(item), app_dir / item.name)


def install_requirements(app_dir: Path = APP_DIR) -> None:
    req = app_dir / "requirements.txt"
    if not req.exists():
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    res = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q",
                          "-r", str(req)], capture_output=True, text=True, creationflags=flags)
    if res.returncode != 0:
        raise RuntimeError("pip: " + (res.stderr or res.stdout).strip()[-500:])


def download_and_install(url: str, progress=lambda text: None, app_dir: Path = APP_DIR) -> None:
    reason = can_self_update()
    if reason:
        raise RuntimeError(reason)
    with tempfile.TemporaryDirectory(prefix="sc-dmx-dl-") as tmp:
        zpath = Path(tmp) / "update.zip"
        progress("Завантаження…")
        with _open(url, timeout=60) as resp, open(zpath, "wb") as fh:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while chunk := resp.read(65536):
                fh.write(chunk)
                done += len(chunk)
                if total:
                    progress(f"Завантаження… {done * 100 // total}%")
        progress("Встановлення файлів…")
        install_from_zip(zpath, app_dir)
    progress("Встановлення залежностей…")
    try:
        install_requirements(app_dir)
    except Exception:
        # без потрібних компонентів нова версія може не запуститися, а оновлення вже не
        # пропонувалося б (версія «нова») — повертаємо попередню версію
        log.exception("Компоненти нової версії не встановилися — повертаю попередню версію")
        restore_backup(app_dir)
        raise
