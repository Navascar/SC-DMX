"""Вікно запуску SC DMX.

З'являється одразу після запуску програми, ще до того, як завантажиться вбудований браузер
інтерфейсу, тож видно, що програма запускається. Поки воно відкрите:
  1. чекає, поки запуститься сервер програми;
  2. чекає першої перевірки оновлень;
  3. якщо є новіша версія — програма не відкривається, доки її не встановити: вікно показує,
     що нового, і кнопку «Оновити». Після оновлення сервер перезапускається, і програма відкривається
     вже в новій версії. Без інтернету або якщо оновлення не можна встановити (робоча копія git,
     немає прав на запис) — програма відкривається як зазвичай.

Логіка рішень — у decide() (без Qt, перевіряється в tests/).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable
from urllib.request import ProxyHandler, Request, build_opener

ICON = Path(__file__).resolve().parent / "static" / "icon.ico"
CHECK_WAIT_S = 20      # довше на перевірку оновлень не чекаємо (повільний інтернет)
SERVER_WAIT_S = 90     # сервер так і не запустився — показуємо помилку
SPLASH_HEADER = "X-SCDMX-Splash"

# Кольори — з дизайн-системи інтерфейсу (style.css)
BG, SURFACE, RAISED, LINE, LINE_STRONG = "#0f1115", "#171a21", "#1f232c", "#2b303b", "#3d4452"
TEXT, MUTED, ACCENT, DANGER = "#e6e8ee", "#9aa1ae", "#4f8cff", "#ef5b60"
ACCENT_STRONG = "#3570d9"   # заливка під білим текстом (контраст 4.7:1)


def decide(upd: dict | None, waited_s: float, requested: bool) -> str:
    """Що показувати вікну запуску.

    upd — стан оновлення від сервера (None — сервер ще не відповідає або перезапускається);
    waited_s — скільки секунд сервер уже відповідає; requested — користувач натиснув «Оновити».
    Повертає: wait · checking · update · installing · failed · open.
    """
    if upd is None:
        return "installing" if requested else "wait"
    status = upd.get("status")
    if status in ("installing", "restarting"):
        return "installing"
    if requested:
        return "failed" if upd.get("error") else "installing"
    if not upd.get("checked") and waited_s < CHECK_WAIT_S:
        return "checking"
    if upd.get("available") and not upd.get("blocked"):
        return "update"
    return "open"


def progress_percent(text: str) -> int | None:
    m = re.search(r"(\d{1,3})\s*%", text or "")
    return min(100, int(m.group(1))) if m else None


def short_notes(notes: str, limit: int = 6) -> str:
    """Перші пункти «Що нового» — коротко, без markdown."""
    lines = [re.sub(r"^[-*]\s*", "• ", ln.strip()) for ln in (notes or "").splitlines() if ln.strip()]
    lines = [ln for ln in lines if not ln.startswith("#")]
    more = len(lines) > limit
    return "\n".join(lines[:limit]) + ("\n…" if more else "")


class Api:
    """Запити до сервера програми (лише 127.0.0.1, без проксі)."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.opener = build_opener(ProxyHandler({}))

    def call(self, path: str, post: bool = False) -> dict | None:
        req = Request(self.base + path, data=b"" if post else None, method="POST" if post else "GET",
                      headers={SPLASH_HEADER: "1"})
        try:
            with self.opener.open(req, timeout=1.5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 — сервер ще стартує або перезапускається
            return None


def run_splash(url: str, version: str, on_open: Callable[[], None], log=lambda text: None):
    """Показує вікно запуску (QApplication уже створено). on_open — відкрити програму.
    Повертає віджет вікна (його треба тримати, поки воно відкрите)."""
    from PySide6.QtCore import QPoint, Qt, QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                                   QProgressBar, QPushButton, QVBoxLayout, QWidget)
    from PySide6.QtGui import QColor

    api = Api(url)
    font = '"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif'

    win = QWidget()
    win.setWindowTitle("SC DMX")
    win.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    win.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    if ICON.exists():
        win.setWindowIcon(QIcon(str(ICON)))
    win.setStyleSheet(f"""
        QWidget {{ font-family: {font}; font-size: 14px; color: {TEXT}; }}
        #panel {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 14px; }}
        #muted {{ color: {MUTED}; font-size: 12px; }}
        #heading {{ font-size: 20px; font-weight: 600; }}
        #notes {{ color: {TEXT}; font-size: 12px; background: {RAISED}; border-radius: 10px; padding: 10px 12px; }}
        #error {{ color: {TEXT}; font-size: 12px; background: #2a1a1c; border: 1px solid {DANGER};
                  border-radius: 10px; padding: 10px 12px; }}
        #footer {{ border-top: 1px solid {LINE}; }}
        QPushButton {{ height: 34px; padding: 0 14px; border-radius: 10px; font-weight: 500;
                       background: {RAISED}; border: 1px solid {LINE}; color: {TEXT}; }}
        QPushButton:hover {{ border-color: {LINE_STRONG}; }}
        QPushButton:focus {{ border-color: {ACCENT}; outline: none; }}
        QPushButton#primary {{ background: {ACCENT_STRONG}; border-color: {ACCENT_STRONG}; color: white; }}
        QPushButton#primary:hover {{ background: #2f63c4; }}
        QProgressBar {{ background: {LINE}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
        QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
    """)
    outer = QVBoxLayout(win)
    outer.setContentsMargins(16, 16, 16, 16)
    panel = QFrame(objectName="panel")
    shadow = QGraphicsDropShadowEffect(blurRadius=24, offset=QPoint(0, 4))
    shadow.setColor(QColor(0, 0, 0, 115))
    panel.setGraphicsEffect(shadow)
    outer.addWidget(panel)
    box = QVBoxLayout(panel)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(0)

    # заголовок: логотип, назва, версія — за нього вікно можна перетягувати
    head = QHBoxLayout()
    head.setContentsMargins(20, 16, 20, 0)
    logo = QLabel()
    if ICON.exists():
        logo.setPixmap(QIcon(str(ICON)).pixmap(28, 28))
    name = QLabel("SC DMX")
    name.setStyleSheet("font-size: 16px; font-weight: 600;")
    ver = QLabel(version, objectName="muted")
    head.addWidget(logo)
    head.addSpacing(10)
    head.addWidget(name)
    head.addSpacing(8)
    head.addWidget(ver)
    head.addStretch(1)
    box.addLayout(head)

    body = QVBoxLayout()
    body.setContentsMargins(24, 18, 24, 22)
    body.setSpacing(0)
    heading = QLabel("Запуск SC DMX", objectName="heading")
    status = QLabel("Запуск програми…", objectName="muted")
    status.setWordWrap(True)
    bar = QProgressBar(textVisible=False)
    bar.setRange(0, 0)                      # поки невідомо, скільки чекати, — смуга «біжить»
    notes = QLabel(objectName="notes")
    notes.setWordWrap(True)
    notes.hide()
    error = QLabel(objectName="error")
    error.setWordWrap(True)
    error.hide()
    body.addWidget(heading)
    body.addSpacing(6)
    body.addWidget(status)
    body.addSpacing(18)
    body.addWidget(bar)
    body.addWidget(notes)
    body.addSpacing(12)
    body.addWidget(error)
    box.addLayout(body)

    # Список змін і текст помилки приходять ззовні (GitHub, виняток) — показуємо лише як текст,
    # без HTML: QLabel інакше сам вгадує формат і відобразив би теги.
    for label in (name, ver, heading, status, notes, error):
        label.setTextFormat(Qt.TextFormat.PlainText)

    footer = QFrame(objectName="footer")
    foot = QHBoxLayout(footer)
    foot.setContentsMargins(24, 14, 24, 14)
    foot.addStretch(1)
    close_btn = QPushButton("Закрити")
    main_btn = QPushButton("Оновити", objectName="primary")
    main_btn.setDefault(True)
    foot.addWidget(close_btn)
    foot.addSpacing(8)
    foot.addWidget(main_btn)
    footer.hide()
    box.addWidget(footer)

    win.setFixedWidth(560)
    state = {"phase": "", "requested": False, "since": None, "t0": time.monotonic(), "closing": False,
             "restarted": False, "drag": None, "was_up": False}

    def show_phase(phase: str, upd: dict | None):
        if phase == state["phase"] and phase != "installing":
            return
        if phase != state["phase"]:
            log(f"Вікно запуску: {phase}")
        state["phase"] = phase
        notes.hide()
        error.hide()
        footer.hide()
        bar.show()
        if phase == "wait":
            heading.setText("Запуск SC DMX")
            status.setText("Перезапуск після оновлення…" if state["restarted"] else "Запуск програми…")
        elif phase == "checking":
            heading.setText("Запуск SC DMX")
            status.setText("Перевірка оновлень…")
        elif phase == "update":
            heading.setText(f"Доступна версія {upd.get('latest', '')}")
            status.setText(f"Встановлена версія {upd.get('current', version)}. Щоб працювати далі, оновіть програму: "
                           "це займе хвилину, сцени й налаштування збережуться.")
            text = short_notes(upd.get("notes", ""))
            if text:
                notes.setText(text)
                notes.show()
            bar.hide()
            main_btn.setText("Оновити")
            footer.show()
            main_btn.setFocus()
        elif phase == "installing":
            heading.setText("Оновлення SC DMX")
            text = (upd or {}).get("progress") or ("Перезапуск…" if upd is None else "Підготовка…")
            status.setText(text)
            pct = progress_percent(text)
            if pct is None:
                bar.setRange(0, 0)
            else:
                bar.setRange(0, 100)
                bar.setValue(pct)
        elif phase == "failed":
            heading.setText("Не вдалося оновити")
            status.setText("Перевірте підключення до інтернету й спробуйте ще раз.")
            error.setText(upd.get("error", ""))
            error.show()
            bar.hide()
            main_btn.setText("Спробувати ще раз")
            footer.show()
        elif phase == "server_error":
            heading.setText("Не вдалося запустити")
            status.setText("Закрийте вікно й відкрийте SC DMX знову. Подробиці — у файлі sc-dmx.log у теці програми.")
            bar.hide()
            main_btn.hide()
            footer.show()
        win.adjustSize()

    def tick():
        if state["closing"]:
            return
        upd = api.call("/api/update")
        now = time.monotonic()
        if upd is None:
            state["since"] = None
            if state["requested"]:
                state["restarted"] = True     # сервер перезапускається вже з новою версією
            # сервер так і не запустився, або працював і зник не через оновлення (збій)
            if not state["requested"] and (state["was_up"] or now - state["t0"] > SERVER_WAIT_S):
                timer.stop()
                show_phase("server_error", None)
                return
        else:
            state["was_up"] = True
            if state["since"] is None:
                state["since"] = now
            if state["restarted"] and upd.get("status") == "idle":
                state["requested"] = False    # нова версія запустилась — далі звичайна перевірка
        phase = decide(upd, now - (state["since"] or now), state["requested"])
        if phase == "open":
            timer.stop()
            state["closing"] = True
            log(f"Вікно запуску: відкриття програми через {now - state['t0']:.1f} с")
            on_open()
            win.close()
            return
        show_phase(phase, upd)

    def on_main():
        if state["phase"] in ("update", "failed"):
            state["requested"] = True
            state["restarted"] = False
            api.call("/api/update", post=True)
            show_phase("installing", {"progress": "Підготовка…"})

    def on_close():
        win.close()

    def close_event(event):
        """Закриття вікна запуску — кнопкою «Закрити», Alt+F4 чи з панелі задач."""
        event.accept()
        if state["closing"]:
            return   # програму вже відкрито (або вікно закривається вдруге)
        state["closing"] = True
        timer.stop()
        api.call("/api/quit", post=True)   # програму так і не відкрили — сервер теж вимикаємо
        QApplication.instance().quit()

    win.closeEvent = close_event

    main_btn.clicked.connect(on_main)
    close_btn.clicked.connect(on_close)

    def press(event):
        if event.button() == Qt.MouseButton.LeftButton:
            state["drag"] = event.globalPosition().toPoint() - win.frameGeometry().topLeft()

    def move(event):
        if state["drag"] is not None and event.buttons() & Qt.MouseButton.LeftButton:
            win.move(event.globalPosition().toPoint() - state["drag"])

    win.mousePressEvent = press
    win.mouseMoveEvent = move
    win.mouseReleaseEvent = lambda _e: state.update(drag=None)

    timer = QTimer(win)
    timer.timeout.connect(tick)
    timer.start(300)
    win.adjustSize()
    screen = QApplication.primaryScreen().availableGeometry()
    win.move(screen.center() - win.rect().center())
    win.show()
    QTimer.singleShot(0, tick)
    return win
