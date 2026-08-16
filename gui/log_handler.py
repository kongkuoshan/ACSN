# gui/log_handler.py
"""
日志 → Qt 信号 中继器 (批量刷新版)

将 Python logging 模块的输出通过线程安全队列收集，
由主线程的 QTimer 定时批量转发到 GUI 文本框。

关键设计:
  - QLogHandler.emit() 只做 queue.put()，不做任何 Qt 操作，
    因此可以从任意工作线程安全调用，也避免了向已销毁 QObject 发信号的问题。
  - LogSignal 持有 QTimer，每 interval_ms 把积压日志一次性 emit，
    主线程只做低频率批量刷新，避免高频日志拖垮事件循环。
"""

import logging
import queue
from PySide6.QtCore import QObject, Signal, QTimer


class LogSignal(QObject):
    """持有日志队列与刷新定时器，批量发射日志文本"""
    message = Signal(str)  # 批量文本 (多行，以 \n 连接)

    def __init__(self, flush_interval_ms: int = 150, parent=None):
        super().__init__(parent)
        self.queue = queue.Queue()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._flush)
        self._timer.start(flush_interval_ms)

    def _flush(self):
        """定时回调 (主线程): 一次性取出队列中所有日志并批量发射"""
        lines = []
        while True:
            try:
                lines.append(self.queue.get_nowait())
            except queue.Empty:
                break
        if lines:
            self.message.emit("\n".join(lines))


class QLogHandler(logging.Handler):
    """
    自定义 logging.Handler，将日志记录格式化后写入线程安全队列。
    不直接发射 Qt 信号，跨线程安全。
    """

    def __init__(self, signal: LogSignal):
        super().__init__()
        self._queue = signal.queue
        self.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        ))

    def emit(self, record: logging.LogRecord):
        """将日志记录格式化后放入队列 (线程安全)"""
        try:
            self._queue.put(self.format(record))
        except Exception:
            # 日志处理器绝不应抛出异常
            pass


def install_gui_logger(target_signal: LogSignal, level: int = logging.INFO):
    """
    安装 GUI 日志处理器，将日志输出重定向到 GUI 队列。

    参数:
        target_signal: LogSignal 实例，连接到 GUI 文本框
        level: 最低日志级别 (默认 INFO)
    """
    handler = QLogHandler(target_signal)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    return handler
