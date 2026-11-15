"""Власне вікно SC DMX на Qt WebEngine.

Вбудований рушій Chromium з PySide6 — програма не залежить від Edge, Chrome
чи будь-якого встановленого браузера й не потребує інтернету: інтерфейс
завантажується з локального сервера програми (127.0.0.1).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

ICON = Path(__file__).resolve().parent / "static" / "icon.ico"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
APP_ID = "SCDMX.Controller"          # власний ідентифікатор для панелі задач Windows
CLOSE_SIGNAL = "__SCDMX_CLOSE__"     # заголовок сторінки, яким інтерфейс просить закрити вікно


def available() -> bool:
    """Чи встановлено Qt WebEngine (пакет PySide6-WebEngine)."""
    try:
        import PySide6.QtWebEngineWidgets  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 — немає пакета або системних бібліотек
        return False


def run_window(url: str, should_close: Callable[[], bool] = lambda: False) -> int:
    """Показує вікно з інтерфейсом. Повертається, коли вікно закрито."""
    # без зайвих фонових сервісів Chromium; працює і без інтернету
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                          "--disable-background-networking --disable-component-update")
    from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
    from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication, QMainWindow

    if sys.platform == "win32":
        # Інакше Windows вважає вікно частиною pythonw.exe і показує в панелі задач іконку Python
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:  # noqa: BLE001
            pass
    from PySide6.QtWidgets import QMessageBox

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("SC DMX")
    app.setOrganizationName("SC DMX")
    if ICON.exists():
        app.setWindowIcon(QIcon(str(ICON)))

    def is_external(qurl: QUrl) -> bool:
        return qurl.scheme() in ("http", "https") and qurl.host() not in LOCAL_HOSTS

    class Page(QWebEnginePage):
        """Зовнішні посилання — у браузері за замовчуванням, а не у вікні програми."""

        def acceptNavigationRequest(self, qurl, nav_type, is_main_frame):  # noqa: N802 (Qt API)
            if is_external(qurl):
                QDesktopServices.openUrl(qurl)
                return False
            return super().acceptNavigationRequest(qurl, nav_type, is_main_frame)

        def createWindow(self, _type):  # noqa: N802 — window.open / target=_blank
            popup = Page(self.profile(), self)
            popup.urlChanged.connect(lambda u: (QDesktopServices.openUrl(u) if is_external(u) else None,
                                                popup.deleteLater()))
            return popup

    win = QMainWindow()
    win.setWindowTitle("SC DMX")
    view = QWebEngineView(win)
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # меню — власне, у самій програмі
    view.setPage(Page(QWebEngineProfile.defaultProfile(), view))
    view.load(QUrl(url))
    win.setCentralWidget(view)

    QShortcut(QKeySequence("F5"), win, activated=view.reload)
    QShortcut(QKeySequence("Ctrl+0"), win, activated=lambda: view.setZoomFactor(1.0))

    settings = QSettings()
    geometry = settings.value("window/geometry")
    if geometry is None or not win.restoreGeometry(geometry):
        win.resize(1440, 900)

    if ICON.exists():
        win.setWindowIcon(QIcon(str(ICON)))

    # Закриття — лише після підтвердження: власне вікно інтерфейсу, а якщо інтерфейс
    # недоступний (немає звʼязку з програмою) — системне вікно Qt.
    state = {"force": False}
    orig_close = win.closeEvent

    def force_close():
        state["force"] = True
        win.close()

    def ask_native():
        box = QMessageBox(QMessageBox.Icon.Question, "SC DMX", "Закрити SC DMX?\nПрожектори згаснуть.", parent=win)
        yes = box.addButton("Закрити", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Скасувати", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is yes:
            force_close()

    def close_event(event):
        settings.setValue("window/geometry", win.saveGeometry())
        if state["force"]:
            orig_close(event)
            return
        event.ignore()
        view.page().runJavaScript("window.scdmxRequestClose ? window.scdmxRequestClose() : 'none'", 0,
                                  lambda result: None if result == "asked" else ask_native())

    win.closeEvent = close_event
    # інтерфейс підтвердив закриття (програму вимкнено) — закриваємо вікно
    view.titleChanged.connect(lambda t: t == CLOSE_SIGNAL and force_close())

    # сервер завершився сам (кнопка «Вимкнути програму») — закриваємо й вікно
    timer = QTimer(win)
    timer.timeout.connect(lambda: should_close() and force_close())
    timer.start(500)

    win.show()
    return app.exec()


if __name__ == "__main__":  # ручна перевірка: python -m dmxctl.window http://127.0.0.1:8080/
    raise SystemExit(run_window(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080/"))
