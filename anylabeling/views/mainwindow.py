"""This module defines the main application window"""

import ctypes
import os.path as osp
import struct

from PyQt5 import QtCore
from PyQt5.QtWidgets import QMainWindow, QStatusBar, QVBoxLayout, QWidget

from ..app_info import __appdescription__, __appname__
from .labeling.label_wrapper import LabelingWrapper
from .labeling.logger import logger

WM_COPYDATA = 0x004A


class COPYDATASTRUCT(ctypes.Structure):
    _fields_ = [
        ("dwData", ctypes.c_void_p),
        ("cbData", ctypes.c_uint32),
        ("lpData", ctypes.c_void_p),
    ]


class MainWindow(QMainWindow):

    def __init__(
        self,
        app,
        config=None,
        filename=None,
        output=None,
        output_file=None,
        output_dir=None,
    ):
        super().__init__()
        self.app = app
        self.config = config or {}
        self.app_name = (
            str(self.config.get("app_name") or __appname__).strip()
            or __appname__
        )

        self.setContentsMargins(0, 0, 0, 0)
        self.setWindowTitle(self.app_name)

        self.menu_bar = self.menuBar()
        self.setMenuBar(self.menu_bar)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.labeling_widget = LabelingWrapper(
            self,
            config=config,
            filename=filename,
            output=output,
            output_file=output_file,
            output_dir=output_dir,
        )
        main_layout.addWidget(self.labeling_widget)
        widget = QWidget()
        widget.setLayout(main_layout)
        self.setCentralWidget(widget)

        status_bar = QStatusBar()
        status_bar.showMessage(f"{self.app_name} - {__appdescription__}")
        self.setStatusBar(status_bar)

    def nativeEvent(self, event_type, message):
        if event_type != b"windows_generic_MSG":
            return False, 0
        raw = ctypes.string_at(int(message), 48)
        msg_code = struct.unpack_from("I", raw, 8)[0]
        if msg_code == WM_COPYDATA:
            lparam_val = struct.unpack_from("Q", raw, 24)[0]
            cds = COPYDATASTRUCT.from_address(lparam_val)
            data = ctypes.string_at(cds.lpData, cds.cbData).decode("utf-8")
            if data:
                # 延迟处理：将 import_image_folder 从 nativeEvent
                # 中移出，避免在 Windows 消息处理上下文中执行重量级 IO
                # 当 viewer dialog 打开时，同步更新其图片列表会导致
                # 消息泵中产生重入问题
                QtCore.QTimer.singleShot(0, lambda: self._do_open_external_path(data))
            return True, 0
        return False, 0

    def _do_open_external_path(self, path):
        path = path.strip('"')
        if not path:
            return
        try:
            path_to_log = osp.realpath(path)
        except Exception:
            path_to_log = path
        logger.info(path_to_log)
        view = self.labeling_widget.view
        if osp.isdir(path):
            view.import_image_folder(path)
        elif osp.isfile(path):
            view.import_image_folder(osp.dirname(path))
            if path in view.fn_to_index:
                view.load_file(path)
        self.showMaximized()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        self.labeling_widget.closeEvent(event)
