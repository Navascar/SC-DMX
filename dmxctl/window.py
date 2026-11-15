"""Власне вікно SC DMX на Qt WebEngine.

Вбудований рушій Chromium з PySide6 — програма не залежить від Edge, Chrome
чи будь-якого встановленого браузера й не потребує інтернету: інтерфейс
завантажується з локального сервера програми (127.0.0.1).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

ICON = Path(__file__).resolve().parent / "static" / "icon.ico"
ICON_SVG = Path(__file__).resolve().parent / "static" / "icon.svg"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
BG = "#0f1115"                       # фон інтерфейсу (style.css: --bg) — без білого спалаху
SERVER_WAIT_S = 90                   # скільки чекати на сервер програми під час запуску
_WINDOW_GUARD = None                 # м'ютекс «вікно вже відкрите» (Windows)
CLOSE_SIGNAL = "__SCDMX_CLOSE__"     # заголовок сторінки, яким інтерфейс просить закрити вікно
LOG = Path(__file__).resolve().parent.parent / "sc-dmx-window.log"


def wlog(text: str) -> None:
    """Журнал вікна (sc-dmx-window.log поруч із програмою): завантаження сторінки, збої рушія, помилки JS."""
    try:
        if LOG.exists() and LOG.stat().st_size > 500_000:
            LOG.unlink()
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{os.getpid()}] {text}\n")
    except OSError:
        pass


def available() -> bool:
    """Чи встановлено Qt WebEngine (пакет PySide6-WebEngine)."""
    try:
        import PySide6.QtWebEngineWidgets  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 — немає пакета або системних бібліотек
        return False


def loading_html(text: str, error: bool = False) -> str:
    """Екран завантаження у стилі інтерфейсу (кольори й шрифт — як у style.css)."""
    import html
    try:
        logo = ICON_SVG.read_text("utf-8")
    except OSError:
        logo = ""
    color = "#ff6b6b" if error else "#9aa1ae"
    spinner = "" if error else '<div class="spin"></div>'
    return f"""<!doctype html><html lang="uk"><meta charset="utf-8"><style>
html,body{{margin:0;height:100%;background:{BG};color:#e6e8ee;
  font:14px/1.45 system-ui,"Segoe UI",Roboto,sans-serif;user-select:none;cursor:default}}
body{{display:grid;place-items:center}}
.box{{display:grid;justify-items:center;gap:16px;text-align:center;max-width:420px;padding:24px}}
.logo svg{{width:72px;height:72px;display:block}}
h1{{margin:0;font-size:20px;letter-spacing:.02em}}
p{{margin:0;color:{color};font-size:12px}}
.spin{{width:22px;height:22px;border-radius:50%;border:2px solid #2b303b;border-top-color:#4f8cff;
  animation:r .8s linear infinite}}
@keyframes r{{to{{transform:rotate(360deg)}}}}
</style><div class="box"><div class="logo">{logo}</div><h1>SC DMX</h1>{spinner}<p>{html.escape(text)}</p></div></html>"""


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

    from PySide6.QtGui import QColor
    if sys.platform == "win32":
        from . import winshell
        # лише одне вікно програми: якщо воно вже є — показуємо його й виходимо
        global _WINDOW_GUARD
        _WINDOW_GUARD = winshell.single_instance(winshell.WINDOW_MUTEX)
        if _WINDOW_GUARD is None:
            for _ in range(50):
                hwnd = winshell.find_app_window()
                if hwnd:
                    winshell.focus_window(hwnd)
                    break
                time.sleep(0.2)
            return 0
        # Інакше Windows вважає вікно частиною pythonw.exe і показує в панелі задач «Python»
        winshell.set_process_id()
    from PySide6.QtWidgets import QFileDialog, QMessageBox

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

        def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802 (Qt API)
            wlog(f"JS {getattr(level, 'name', level)}: {message} ({source}:{line})")

        def createWindow(self, _type):  # noqa: N802 — window.open / target=_blank
            popup = Page(self.profile(), self)
            popup.urlChanged.connect(lambda u: (QDesktopServices.openUrl(u) if is_external(u) else None,
                                                popup.deleteLater()))
            return popup

    import PySide6
    wlog(f"Вікно: {url} · Qt {PySide6.__version__} · {os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')}")
    win = QMainWindow()
    win.setWindowTitle("SC DMX")
    view = QWebEngineView(win)
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # меню — власне, у самій програмі
    view.setPage(Page(QWebEngineProfile.defaultProfile(), view))
    # Поки вбудований Chromium стартує (уперше — кілька секунд) і поки запускається сервер,
    # вікно показує екран завантаження у стилі програми, а не біле поле.
    win.setStyleSheet(f"QMainWindow, QWebEngineView {{ background: {BG}; }}")
    view.page().setBackgroundColor(QColor(BG))
    view.setHtml(loading_html("Запуск…"))
    win.setCentralWidget(view)

    retries = {"n": 0}

    def repaint():
        """Іноді (перший старт вбудованого Chromium) сторінка завантажена, але вікно лишається порожнім,
        доки його не змінити в розмірі. Тож після завантаження вікно примусово перемальовується."""
        size = view.size()
        view.resize(size.width() - 1, size.height())
        QTimer.singleShot(60, lambda: (view.resize(size), view.update()))

    def verify():
        """Інтерфейс справді з'явився? Якщо ні — завантажуємо сторінку ще раз."""
        if not boot["loaded"] or view.url().toString() != url:
            return

        def check(ready):
            if ready is True:
                wlog("Інтерфейс показано")
                repaint()
            elif retries["n"] < 20:
                retries["n"] += 1
                wlog(f"Інтерфейс не з'явився ({ready!r}) — перезавантаження")
                view.load(QUrl(url))
        view.page().runJavaScript("!!(document.body && document.querySelector('#outputText'))", 0, check)

    def on_load_finished(ok: bool):
        current = view.url().toString()
        wlog(f"Сторінка завантажена: ok={ok} url={current or '(екран завантаження)'}")
        if ok:
            repaint()
            if current == url:
                QTimer.singleShot(1500, verify)
        elif boot["loaded"] and retries["n"] < 20:
            retries["n"] += 1          # сервер ще не відповідає — пробуємо ще раз
            QTimer.singleShot(1000, lambda: view.load(QUrl(url)))

    def on_render_gone(status, code):
        wlog(f"Процес рушія завершився: {getattr(status, 'name', status)} код {code} — перезавантаження")
        QTimer.singleShot(500, lambda: view.load(QUrl(url)) if boot["loaded"] else view.setHtml(loading_html("Запуск…")))

    view.loadFinished.connect(on_load_finished)
    view.page().renderProcessTerminated.connect(on_render_gone)

    def server_ready() -> bool:
        import socket
        parts = QUrl(url)
        try:
            with socket.create_connection((parts.host() or "127.0.0.1", parts.port(80)), timeout=0.3):
                return True
        except OSError:
            return False

    boot = {"t0": time.monotonic(), "loaded": False}

    def try_load():
        if boot["loaded"]:
            return
        if server_ready():
            boot["loaded"] = True
            wlog(f"Сервер відповідає через {time.monotonic() - boot['t0']:.1f} с, завантаження інтерфейсу")
            view.load(QUrl(url))
        elif time.monotonic() - boot["t0"] > SERVER_WAIT_S:
            boot["loaded"] = True
            wlog("Сервер не запустився")
            view.setHtml(loading_html("Не вдалося запустити програму. Закрийте вікно й відкрийте SC DMX знову.", error=True))
        else:
            QTimer.singleShot(250, try_load)

    QTimer.singleShot(0, try_load)

    # Файли, які віддає програма (напр. сцена .scdmx), — через діалог «Зберегти як»
    def on_download(req):
        name = req.downloadFileName() or "scene.scdmx"
        last = settings.value("files/dir") or str(Path.home() / "Documents")
        ext = Path(name).suffix
        flt = f"Сцена SC DMX (*{ext});;Усі файли (*)" if ext == ".scdmx" else "Усі файли (*)"
        path, _ = QFileDialog.getSaveFileName(win, "Зберегти файл", str(Path(last) / name), flt)
        if not path:
            req.cancel()
            return
        target = Path(path)
        settings.setValue("files/dir", str(target.parent))
        req.setDownloadDirectory(str(target.parent))
        req.setDownloadFileName(target.name)

        def done():
            if req.isFinished():
                ok = req.state() == req.DownloadState.DownloadCompleted
                msg = f"Файл збережено: {target.name}" if ok else "Не вдалося зберегти файл"
                view.page().runJavaScript(f"window.scdmxToast && window.scdmxToast({json.dumps(msg)}, {str(ok).lower()})")
        req.isFinishedChanged.connect(done)
        req.accept()

    view.page().profile().downloadRequested.connect(on_download)

    QShortcut(QKeySequence("F5"), win, activated=view.reload)
    QShortcut(QKeySequence("Ctrl+0"), win, activated=lambda: view.setZoomFactor(1.0))

    settings = QSettings()
    geometry = settings.value("window/geometry")
    if geometry is None or not win.restoreGeometry(geometry):
        win.resize(1440, 900)

    if ICON.exists():
        win.setWindowIcon(QIcon(str(ICON)))

    if sys.platform == "win32":
        # ще до показу: заголовок у кольорах програми й «SC DMX» на панелі задач замість «Python»
        hwnd = int(win.winId())
        for step in (winshell.style_title_bar, winshell.set_window_identity):
            try:
                step(hwnd)
            except Exception:  # noqa: BLE001 — старі Windows або немає pywin32: просто без цього
                pass
        try:
            winshell.repair_shortcuts()   # ярлики старих версій — з ідентифікатором застосунку
        except Exception:  # noqa: BLE001
            pass

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
    wlog("Вікно показано")
    QTimer.singleShot(300, repaint)
    code = app.exec()
    wlog(f"Вікно закрито, код {code}")
    return code


if __name__ == "__main__":  # ручна перевірка: python -m dmxctl.window http://127.0.0.1:8080/
    raise SystemExit(run_window(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080/"))
