# gui/log_handler.py
"""
日志 → Qt 信号 中继器

将 Python logging 模块的输出实时转发到 Qt 主线程的信号槽，
使得日志可以在 GUI 的 QPlainTextEdit 中实时显示。
"""

import logging
from PySide6.QtCore import QObject, Signal


class LogSignal(QObject):
    """Qt 信号发射器：携带日志消息和级别"""
    message = Signal(str, int)  # (formatted_message, levelno)


class QLogHandler(logging.Handler):
    """
    自定义 logging.Handler，将日志记录转发为 Qt Signal。
    自动处理跨线程安全问题。
    """

    def __init__(self, signal: LogSignal):
        super().__init__()
        self.signal = signal
        self.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        ))

    def emit(self, record: logging.LogRecord):
        """将日志记录格式化为字符串并通过 Qt 信号发射"""
        msg = self.format(record)
        self.signal.message.emit(msg, record.levelno)


def install_gui_logger(target_signal: LogSignal, level: int = logging.INFO):
    """
    安装 GUI 日志处理器，将日志输出重定向到 GUI 信号。

    参数:
        target_signal: LogSignal 实例，连接到 GUI 文本框
        level: 最低日志级别 (默认 INFO)
    """
    handler = QLogHandler(target_signal)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    return handler
