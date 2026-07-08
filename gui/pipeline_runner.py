# gui/pipeline_runner.py
"""
流水线执行器 — QThread 封装

在后台线程中运行 AcademicPipeline 的各个阶段,
通过 Qt 信号向主线程 GUI 报告进度和日志。
"""

import os
import traceback
import copy
from PySide6.QtCore import QThread, Signal

from pipelines.data_pipeline import AcademicPipeline


class PipelineRunner(QThread):
    """
    后台流水线执行线程。

    信号:
        stage_started(str): 阶段开始 (阶段名称)
        stage_completed(str, bool): 阶段完成 (名称, 是否成功)
        log_line(str): 日志输出
        overall_progress(int, str): 总进度 (百分比, 当前状态描述)
        pipeline_finished(bool, str): 流水线结束 (是否成功, 消息)
    """

    stage_started = Signal(str)
    stage_completed = Signal(str, bool)
    log_line = Signal(str)
    overall_progress = Signal(int, str)
    pipeline_finished = Signal(bool, str)

    # 所有流水线阶段定义
    ALL_STAGES = [
        ("author_mining",  "Step 0: 数据采集与作者画像"),
        ("tagging",        "Step 1: 靶向过滤 (U1.5)"),
        ("cleaning",       "Step 2: 硬规则清洗 (U2)"),
        ("nlp_clustering", "Step 3: NLP 聚类 (U2.5)"),
        ("llm_autofill",   "Step 3.5: LLM 预填 (可选)"),
        ("final_assembly", "Step 4: 终极组装 (U3)"),
        ("analytics",      "Step 4.5: 情报挖掘与演化分析"),
        ("db_import",      "Step 5: 数据库导入"),
        ("dashboard",      "Step 6: 启动大屏"),
    ]

    def __init__(self, config: dict, stages: list = None, parent=None):
        """
        参数:
            config: 完整配置字典 (会被 deepcopy)
            stages: 要执行的阶段列表 (None = 全部执行)
                    格式: ["author_mining", "tagging", ...]
            parent: Qt 父对象
        """
        super().__init__(parent)
        self._config = copy.deepcopy(config)
        self._stages = stages if stages else [s[0] for s in self.ALL_STAGES]
        self._stop_requested = False
        self._stage_methods = {
            "author_mining":  "run_author_mining_stage",
            "tagging":        "run_tagging_stage",
            "cleaning":       "run_cleaning_stage",
            "nlp_clustering": "run_nlp_clustering_stage",
            "llm_autofill":   "run_llm_autofill_stage",
            "final_assembly": "run_final_assembly_stage",
            "analytics":      "run_analytics_stage",
            "db_import":      "run_db_import_stage",
            "dashboard":      "run_dashboard_stage",
        }

    def stop(self):
        """请求停止流水线 (在下一个阶段边界检查)"""
        self._stop_requested = True
        self.log_line.emit("⚠️ 收到停止请求，当前阶段完成后将终止流水线。")

    def run(self):
        """QThread 入口: 按顺序执行选定的流水线阶段"""
        if not self._stages:
            self.log_line.emit("⚠️ 未选择任何执行阶段。")
            self.pipeline_finished.emit(False, "未选择阶段")
            return

        pipeline = AcademicPipeline(self._config)
        stage_names = {s[0]: s[1] for s in self.ALL_STAGES}
        total = len(self._stages)
        success = True

        for idx, stage_key in enumerate(self._stages):
            if self._stop_requested:
                self.log_line.emit("⏹ 流水线已被用户中断。")
                break

            stage_label = stage_names.get(stage_key, stage_key)
            method_name = self._stage_methods.get(stage_key)

            progress_pct = int((idx / total) * 100)
            self.overall_progress.emit(progress_pct, f"正在执行: {stage_label}")
            self.stage_started.emit(stage_label)

            try:
                if method_name and hasattr(pipeline, method_name):
                    method = getattr(pipeline, method_name)
                    # dashboard 阶段使用非阻塞模式
                    if stage_key == "dashboard":
                        method(background=True)
                    else:
                        method()
                    self.stage_completed.emit(stage_label, True)
                else:
                    self.log_line.emit(f"⚠️ 未知阶段: {stage_key}，已跳过。")
                    self.stage_completed.emit(stage_label, False)
            except Exception as e:
                self.log_line.emit(f"❌ 阶段 [{stage_label}] 发生错误: {e}")
                self.log_line.emit(traceback.format_exc())
                self.stage_completed.emit(stage_label, False)
                success = False
                break

            # 更新进度
            progress_pct = int(((idx + 1) / total) * 100)
            self.overall_progress.emit(progress_pct, f"已完成: {stage_label}")

        # 最终完成
        final_pct = 100 if success else int(((idx + 1) / total) * 100)
        self.overall_progress.emit(final_pct, "流水线完成" if success else "流水线中断")
        self.pipeline_finished.emit(success, "流水线全部阶段执行完毕。" if success else f"流水线在 [{stage_label}] 阶段中止。")

    @classmethod
    def get_stage_list(cls):
        """获取所有可用阶段的列表 (供 GUI 复选框使用)"""
        return cls.ALL_STAGES

    @classmethod
    def get_dashboard_only_stages(cls):
        """仅启动大屏的阶段列表"""
        return ["dashboard"]

    @classmethod
    def get_full_pipeline_stages(cls):
        """完整流水线的阶段列表"""
        return [s[0] for s in cls.ALL_STAGES]
