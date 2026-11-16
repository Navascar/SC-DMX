import pytest


@pytest.fixture(autouse=True)
def _no_update_check(monkeypatch):
    """Сервер перевіряє оновлення одразу при запуску — у тестах без звернень до GitHub."""
    from dmxctl import updater

    def offline():
        raise OSError("тести без мережі")
    monkeypatch.setattr(updater, "check", offline)
