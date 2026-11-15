"""Запуск SC DMX без консолі — з ярлика, меню «Пуск» або закріпленої на панелі задач іконки.

pythonw.exe "...\\SC-DMX\\sc-dmx.pyw"  — те саме, що  python -m dmxctl --open  у теці програми.
"""
import os
import runpy
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)
sys.argv = ["dmxctl", *[a for a in sys.argv[1:] if a != "--open"], "--open"]
runpy.run_module("dmxctl", run_name="__main__", alter_sys=True)
