import os

# Temporary fix for: bus error
# Source: https://stackoverflow.com/questions/73072612/
# why-does-np-linalg-solve-raise-bus-error-when-running-on-its-own-thread-mac-m1
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

# Suppress ICC profile warnings
os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.gui.icc=false"

import argparse
import codecs
import logging

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import yaml
from PyQt5 import QtCore, QtWidgets

from anylabeling.app_info import __appname__, __version__, __url__
from anylabeling.config import get_config
from anylabeling import config as anylabeling_config
from anylabeling.views.mainwindow import MainWindow
from anylabeling.views.labeling.logger import logger
from anylabeling.views.labeling.utils import new_icon, gradient_text
from anylabeling.views.labeling.utils.update_checker import (
    check_for_updates_async,
)

# NOTE: Do not remove this import, it is required for loading translations
from anylabeling.resources import resources


def _filter_harmless_qt_warnings():
    """Install a Qt message handler that suppresses harmless warnings.

    QDockWidget "Negative sizes (0,-1)" warning: Qt's internal C++ code
    (during setWidget/addDockWidget/restoreState) calls setMinimumWidth(0)
    which internally does setMinimumSize(0, minimumSize().height()). If
    the height was internally reset to -1, this triggers the warning.
    It is completely harmless — Qt just ignores the negative value.
    """
    def handler(mode, context, message):
        if "Negative sizes" in message and "QDockWidget" in message:
            return  # Suppress harmless warning
        # Default behavior for all other messages
        if mode == QtCore.QtWarningMsg:
            print(f"Qt WARNING: {message}", file=sys.stderr)
        elif mode == QtCore.QtCriticalMsg:
            print(f"Qt CRITICAL: {message}", file=sys.stderr)
        elif mode == QtCore.QtFatalMsg:
            print(f"Qt FATAL: {message}", file=sys.stderr)

    QtCore.qInstallMessageHandler(handler)


_filter_harmless_qt_warnings()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset-config", action="store_true", help="reset qt config"
    )
    parser.add_argument(
        "--logger-level",
        default="info",
        choices=["debug", "info", "warning", "fatal", "error"],
        help="logger level",
    )
    parser.add_argument(
        "--no-auto-update-check",
        action="store_true",
        help="disable automatic update check on startup",
    )
    parser.add_argument(
        "filename",
        nargs="?",
        help=(
            "image or label filename; "
            "If a directory path is passed in, the folder will be loaded automatically"
        ),
    )
    parser.add_argument(
        "--output",
        "-O",
        "-o",
        help=(
            "output file or directory (if it ends with .json it is "
            "recognized as file, else as directory)"
        ),
    )
    default_config_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "xanylabeling_config.ini"
    )
    parser.add_argument(
        "--config",
        dest="config",
        help=(
            "config file or yaml-format string (default:"
            f" {default_config_file})"
        ),
        default=default_config_file,
    )
    # config for the gui
    parser.add_argument(
        "--nodata",
        dest="store_data",
        action="store_false",
        help="stop storing image data to JSON file",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--autosave",
        dest="auto_save",
        action="store_true",
        help="auto save",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--nosortlabels",
        dest="sort_labels",
        action="store_false",
        help="stop sorting labels",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--flags",
        help="comma separated list of flags OR file containing flags",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--labelflags",
        dest="label_flags",
        help=r"yaml string of label specific flags OR file containing json "
        r"string of label specific flags (ex. {person-\d+: [male, tall], "
        r"dog-\d+: [black, brown, white], .*: [occluded]})",  # NOQA
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--labels",
        help="comma separated list of labels OR file containing labels",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--validatelabel",
        dest="validate_label",
        choices=["exact"],
        help="label validation types",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--keep-prev",
        action="store_true",
        help="keep annotation of previous frame",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        help="epsilon to find nearest vertex on canvas",
        default=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if hasattr(args, "flags"):
        if os.path.isfile(args.flags):
            with codecs.open(args.flags, "r", encoding="utf-8") as f:
                args.flags = [line.strip() for line in f if line.strip()]
        else:
            args.flags = [line for line in args.flags.split(",") if line]

    if hasattr(args, "labels"):
        if os.path.isfile(args.labels):
            with codecs.open(args.labels, "r", encoding="utf-8") as f:
                args.labels = [line.strip() for line in f if line.strip()]
        else:
            args.labels = [line for line in args.labels.split(",") if line]

    if hasattr(args, "label_flags"):
        if os.path.isfile(args.label_flags):
            with codecs.open(args.label_flags, "r", encoding="utf-8") as f:
                args.label_flags = yaml.safe_load(f)
        else:
            args.label_flags = yaml.safe_load(args.label_flags)

    config_from_args = args.__dict__
    reset_config = config_from_args.pop("reset_config")
    filename = config_from_args.pop("filename")
    output = config_from_args.pop("output")
    config_file_or_yaml = config_from_args.pop("config")
    logger_level = config_from_args.pop("logger_level")
    no_auto_update_check = config_from_args.pop("no_auto_update_check", False)

    logger.setLevel(getattr(logging, logger_level.upper()))
    logger.info(
        f"🚀 {gradient_text(f'X-AnyLabeling v{__version__} launched!')}"
    )
    logger.info(f"⭐ If you like it, give us a star: {__url__}")
    anylabeling_config.current_config_file = config_file_or_yaml
    config = get_config(config_file_or_yaml, config_from_args, show_msg=True)

    # 强制将语言设置为中文
    config["language"] = "zh_CN"

    if not config["labels"] and config["validate_label"]:
        logger.error(
            "--labels must be specified with --validatelabel or "
            "validate_label: exact in the config file "
            "(ex. ~/.YSGxanylabelingrc)."
        )
        sys.exit(1)

    output_file = None
    output_dir = None
    if output is not None:
        if output.endswith(".json"):
            output_file = output
        else:
            output_dir = output

    language = config.get("language", QtCore.QLocale.system().name())

    # Add a mapping for Chinese locales to ensure consistency
    if language.startswith('zh'):
        language = 'zh_CN'

    translator = QtCore.QTranslator()
    loaded_language = translator.load(
        ":/languages/translations/" + language + ".qm"
    )
    # Enable scaling for high dpi screens
    QtWidgets.QApplication.setAttribute(
        QtCore.Qt.AA_EnableHighDpiScaling, True
    )  # enable highdpi scaling
    QtWidgets.QApplication.setAttribute(
        QtCore.Qt.AA_UseHighDpiPixmaps, True
    )  # use highdpi icons
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)

    app = QtWidgets.QApplication(sys.argv)
    app.processEvents()

    app.setApplicationName(__appname__)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(new_icon("icon"))
    if loaded_language:
        app.installTranslator(translator)
    else:
        logger.warning(
            f"Failed to load translation for {language}. "
            "Using default language.",
        )

    if filename:
        try:
            path_to_log = os.path.realpath(filename)
        except Exception:
            path_to_log = filename
        logger.info(path_to_log)

    win = MainWindow(
        app,
        config=config,
        filename=filename,
        output_file=output_file,
        output_dir=output_dir,
    )

    if reset_config:
        logger.info(f"Resetting Qt config: {win.settings.fileName()}")
        win.settings.clear()
        sys.exit(0)

    if not no_auto_update_check:

        def delayed_update_check():
            check_for_updates_async(timeout=5)

        QtCore.QTimer.singleShot(2000, delayed_update_check)

    # 根据窗口配置文件决定启动行为：有配置按配置来，无配置默认全屏
    # 删除 xanylabeling_window.ini 即可恢复全屏
    window_ini = os.path.join(anylabeling_config._app_dir(), "xanylabeling_window.ini")
    win_settings = QtCore.QSettings(window_ini, QtCore.QSettings.IniFormat)
    was_maximized = win_settings.value("window/maximized", True)
    if isinstance(was_maximized, str):
        was_maximized = was_maximized.lower() in ("true", "1")

    if was_maximized:
        # 强制在系统默认屏幕全屏，不跟随鼠标
        # showMaximized() 会跟随鼠标所在屏幕，所以先 move 到默认屏幕
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            win.move(geo.x() + 100, geo.y() + 100)
        win.showMaximized()
    else:
        win_w = int(win_settings.value("window/width", 1200) or 1200)
        win_h = int(win_settings.value("window/height", 800) or 800)
        win_x = int(win_settings.value("window/x", 0) or 0)
        win_y = int(win_settings.value("window/y", 0) or 0)
        # 不做屏幕边界验证：允许窗口部分飞出屏幕外
        win.resize(win_w, win_h)
        win.move(win_x, win_y)
        win.show()
    win.raise_()

    # Force fit-window after layout settles (first image may have loaded
    # during __init__ before the window was properly sized).
    if filename and win.labeling_widget.view.image_list:
        QtCore.QTimer.singleShot(100,
            lambda: win.labeling_widget.view.adjust_scale(initial=True))

    sys.exit(app.exec())


# this main block is required to generate executable by pyinstaller
if __name__ == "__main__":
    main()
