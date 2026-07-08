# gui/parameter_panel.py
"""
参数配置面板 — 滚动式表单编辑器

将 config.yaml 中的所有参数以分组形式展示在 GUI 中,
支持编辑、保存配置、以及从配置文件重新加载。
"""

import yaml
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QPushButton, QScrollArea, QMessageBox, QLabel
)
from PySide6.QtCore import Signal

from gui.widgets import (
    create_text_row, create_file_row, create_dir_row,
    create_int_row, create_checkbox_row, create_textarea_row,
    make_help_btn
)


class ParameterPanel(QScrollArea):
    """
    可滚动的参数面板。包含所有 config.yaml 参数的 GUI 编辑控件。

    信号:
        config_changed: 参数被修改时发射
        start_requested(stages, mode): 用户点击开始
        stop_requested: 用户点击停止
        deploy_neo4j_requested: 用户点击 Docker 部署
    """

    config_changed = Signal()
    start_requested = Signal(list, str)  # (stages_list, mode_name)
    stop_requested = Signal()
    deploy_neo4j_requested = Signal()

    def __init__(self, config_path: str = "config/config.yaml", parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.config = {}
        self._widgets = {}  # param_key -> widget reference
        self._step_checkboxes = {}  # stage_key -> QCheckBox

        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        # 主容器
        self._container = QWidget()
        self._main_layout = QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(10, 10, 10, 10)
        self._main_layout.setSpacing(8)

        self._build_ui()
        self.setWidget(self._container)

    def _build_ui(self):
        """构建所有参数分组"""
        self._build_institution_group()
        self._build_paths_group()
        self._build_nlp_group()
        self._build_llm_group()
        self._build_database_group()
        self._build_author_matcher_group()
        self._build_analytics_group()
        self._build_control_group()

        # 底部弹性空间
        self._main_layout.addStretch()

    # ================================================================
    # 机构设置
    # ================================================================
    def _build_institution_group(self):
        group = QGroupBox("1. 机构设置 (Institution Settings)")
        layout = QFormLayout()
        layout.setSpacing(8)

        # 目标机构 ID
        _, w = create_text_row("目标机构ID:", param_key="institution.target_id", parent=self)
        self._widgets["institution.target_id"] = w
        layout.addRow(w)

        # 邮箱
        _, w = create_text_row("请求邮箱:", param_key="institution.email", parent=self)
        self._widgets["institution.email"] = w
        layout.addRow(w)

        # 起始年份
        _, w = create_int_row("起始年份:", default=2021, param_key="institution.start_year",
                              min_val=1950, max_val=2030, parent=self)
        self._widgets["institution.start_year"] = w
        layout.addRow(w)

        # 结束年份 (0 = 当前年份)
        _, w = create_int_row("结束年份 (0=至今):", default=0, param_key="institution.end_year",
                              min_val=0, max_val=2030, parent=self)
        self._widgets["institution.end_year"] = w
        layout.addRow(w)

        # 兜底关键词
        _, w = create_textarea_row("兜底关键词:\n(每行一个)", param_key="institution.fallback_keywords",
                                   rows=3, parent=self)
        self._widgets["institution.fallback_keywords"] = w
        layout.addRow(w)

        group.setLayout(layout)
        self._main_layout.addWidget(group)

    # ================================================================
    # 路径配置
    # ================================================================
    def _build_paths_group(self):
        group = QGroupBox("2. 路径配置 (Paths)")
        layout = QFormLayout()
        layout.setSpacing(6)

        path_configs = [
            ("data_u1_raw", "U1 原始数据:"),
            ("data_u1_5_tagged", "U1.5 打标数据:"),
            ("data_u2_cleaned", "U2 清洗数据:"),
            ("data_u2_unique", "U2 唯一实体:"),
            ("data_u2_5_nlp", "U2.5 NLP数据:"),
            ("data_u3_final", "U3 最终数据:"),
            ("input_author_excel", "导师名单(输入):"),
            ("output_author_excel", "作者画像(输出):"),
            ("excel_aff_mapping", "机构映射表:"),
            ("excel_con_mapping", "领域映射表:"),
            ("excel_aff_mapping_ai", "AI机构映射表:"),
            ("excel_con_mapping_ai", "AI领域映射表:"),
        ]

        for key, label in path_configs:
            param_key = f"paths.{key}"
            _, w = create_file_row(label, param_key=param_key, parent=self)
            self._widgets[param_key] = w
            layout.addRow(w)

        group.setLayout(layout)
        self._main_layout.addWidget(group)

    # ================================================================
    # NLP 参数
    # ================================================================
    def _build_nlp_group(self):
        group = QGroupBox("3. NLP 参数 (NLP Parameters)")
        layout = QFormLayout()
        layout.setSpacing(8)

        _, w = create_int_row("目标聚类数:", default=350, param_key="nlp.target_aff_clusters",
                              min_val=50, max_val=2000, parent=self)
        self._widgets["nlp.target_aff_clusters"] = w
        layout.addRow(w)

        group.setLayout(layout)
        self._main_layout.addWidget(group)

    # ================================================================
    # LLM 助手
    # ================================================================
    def _build_llm_group(self):
        group = QGroupBox("4. LLM 助手 (LLM Assistant)")
        layout = QFormLayout()
        layout.setSpacing(8)

        # 启用开关
        _, w = create_checkbox_row("启用 LLM 自动预填", param_key="llm_assistant.enabled", parent=self)
        self._widgets["llm_assistant.enabled"] = w
        layout.addRow(w)

        # API 地址
        _, w = create_text_row("API 地址:", param_key="llm_assistant.api_url", parent=self)
        self._widgets["llm_assistant.api_url"] = w
        layout.addRow(w)

        # 领域分类列表
        _, w = create_textarea_row("领域分类列表:", param_key="llm_assistant.concept_target_fields",
                                   rows=2, parent=self)
        self._widgets["llm_assistant.concept_target_fields"] = w
        layout.addRow(w)

        # 机构识别提示词
        _, w = create_textarea_row("机构识别提示词:", param_key="llm_assistant.affiliation_system_prompt",
                                   rows=3, parent=self)
        self._widgets["llm_assistant.affiliation_system_prompt"] = w
        layout.addRow(w)

        group.setLayout(layout)
        self._main_layout.addWidget(group)

    # ================================================================
    # 数据库
    # ================================================================
    def _build_database_group(self):
        group = QGroupBox("5. 数据库 (Database)")
        layout = QFormLayout()
        layout.setSpacing(8)

        _, w = create_text_row("数据库 URI:", default="bolt://localhost:7688",
                               param_key="database.uri", parent=self)
        self._widgets["database.uri"] = w
        layout.addRow(w)

        _, w = create_text_row("用户名:", default="neo4j",
                               param_key="database.user", parent=self)
        self._widgets["database.user"] = w
        layout.addRow(w)

        _, w = create_text_row("密码:", default="12345678",
                               param_key="database.password", password=True, parent=self)
        self._widgets["database.password"] = w
        layout.addRow(w)

        _, w = create_dir_row("Neo4j Import 目录:", param_key="author_matcher.paths.neo4j_import_dir",
                              parent=self)
        self._widgets["author_matcher.paths.neo4j_import_dir"] = w
        layout.addRow(w)

        # Docker 部署按钮
        btn_deploy = QPushButton("🐳 一键使用 Docker 部署本地 Neo4j")
        btn_deploy.setStyleSheet("background-color: #27ae60; padding: 10px; font-size: 14px;")
        btn_deploy.clicked.connect(self.deploy_neo4j_requested.emit)
        layout.addRow(btn_deploy)

        group.setLayout(layout)
        self._main_layout.addWidget(group)

    # ================================================================
    # 作者匹配
    # ================================================================
    def _build_author_matcher_group(self):
        group = QGroupBox("6. 作者匹配 (Author Matching)")
        layout = QFormLayout()
        layout.setSpacing(8)

        _, w = create_text_row("姓名列名:", default="导师姓名",
                               param_key="author_matcher.name_column", parent=self)
        self._widgets["author_matcher.name_column"] = w
        layout.addRow(w)

        group.setLayout(layout)
        self._main_layout.addWidget(group)

    # ================================================================
    # 操作控制 (非 config 参数)
    # ================================================================
    def _build_control_group(self):
        group = QGroupBox("7. 操作控制 (Actions)")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # 执行模式下拉
        from PySide6.QtWidgets import QComboBox
        mode_label = QLabel("运行模式:")
        mode_label.setStyleSheet("font-weight: bold; color: #CCCCCC; font-size: 13px;")
        layout.addWidget(mode_label)

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("一键启动大屏 (仅查看已有数据)", "dashboard_only")
        self._mode_combo.addItem("完整流水线 (从爬虫到展示)", "full_pipeline")
        self._mode_combo.addItem("分步执行 (自选阶段)", "step_by_step")
        self._mode_combo.setMinimumHeight(32)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self._mode_combo)

        # 分步执行复选框 (默认隐藏)
        from PySide6.QtWidgets import QCheckBox
        from gui.pipeline_runner import PipelineRunner

        self._step_widget = QWidget()
        step_layout = QVBoxLayout(self._step_widget)
        step_layout.setContentsMargins(8, 4, 0, 4)
        step_layout.setSpacing(3)

        for key, label in PipelineRunner.ALL_STAGES:
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setStyleSheet("font-size: 12px; color: #aaa; font-weight: normal; padding: 2px;")
            self._step_checkboxes[key] = cb
            step_layout.addWidget(cb)

        self._step_widget.setVisible(False)
        layout.addWidget(self._step_widget)

        # 按钮行
        from PySide6.QtWidgets import QHBoxLayout
        btn_layout = QHBoxLayout()

        self.btn_start = QPushButton("🚀 开始执行")
        self.btn_start.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold;"
            "padding: 12px; font-size: 15px;"
        )
        self.btn_start.setMinimumHeight(42)
        self.btn_start.clicked.connect(self._on_start_clicked)
        btn_layout.addWidget(self.btn_start, 2)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setStyleSheet(
            "background-color: #c0392b; color: white; font-weight: bold;"
            "padding: 12px; font-size: 13px;"
        )
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        btn_layout.addWidget(self.btn_stop, 1)

        layout.addLayout(btn_layout)

        # 进度条
        from PySide6.QtWidgets import QProgressBar
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setFormat("就绪")
        layout.addWidget(self._progress)

        group.setLayout(layout)
        self._main_layout.addWidget(group)

    # ================================================================
    # 情报分析
    # ================================================================
    def _build_analytics_group(self):
        group = QGroupBox("8. 情报分析 (Analytics)")
        layout = QFormLayout()
        layout.setSpacing(8)

        _, w = create_int_row("概念降维簇数:", default=25,
                               param_key="analytics.concept_clusters",
                               min_val=5, max_val=100, parent=self)
        self._widgets["analytics.concept_clusters"] = w
        layout.addRow(w)

        _, w = create_checkbox_row("使用 LLM 命名概念簇",
                                   param_key="analytics.use_llm_labels", parent=self)
        self._widgets["analytics.use_llm_labels"] = w
        layout.addRow(w)

        group.setLayout(layout)
        self._main_layout.addWidget(group)

    # ================================================================
    # 配置读写
    # ================================================================

    def load_config(self):
        """从 config.yaml 加载配置并填充到 GUI 控件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)

            # 机构设置
            inst = self.config.get('institution', {})
            self._set_text("institution.target_id", inst.get('target_id', ''))
            self._set_text("institution.email", inst.get('email', ''))
            self._set_int("institution.start_year", inst.get('start_year', 2021))
            end_year = inst.get('end_year')
            self._set_int("institution.end_year", end_year if end_year else 0)
            self._set_text("institution.fallback_keywords",
                           '\n'.join(inst.get('fallback_keywords', [])))

            # 路径
            paths = self.config.get('paths', {})
            for key in ["data_u1_raw", "data_u1_5_tagged", "data_u2_cleaned",
                        "data_u2_unique", "data_u2_5_nlp", "data_u3_final",
                        "input_author_excel", "output_author_excel",
                        "excel_aff_mapping", "excel_con_mapping",
                        "excel_aff_mapping_ai", "excel_con_mapping_ai"]:
                self._set_text(f"paths.{key}", paths.get(key, ''))

            # NLP
            nlp = self.config.get('nlp', {})
            self._set_int("nlp.target_aff_clusters", nlp.get('target_aff_clusters', 350))

            # LLM
            llm = self.config.get('llm_assistant', {})
            self._set_check("llm_assistant.enabled", llm.get('enabled', False))
            self._set_text("llm_assistant.api_url", llm.get('api_url', ''))
            self._set_text("llm_assistant.concept_target_fields", llm.get('concept_target_fields', ''))
            self._set_text("llm_assistant.affiliation_system_prompt", llm.get('affiliation_system_prompt', ''))

            # 数据库
            db = self.config.get('database', {})
            self._set_text("database.uri", db.get('uri', 'bolt://localhost:7688'))
            self._set_text("database.user", db.get('user', 'neo4j'))
            self._set_text("database.password", db.get('password', ''))

            # Neo4j import dir
            am = self.config.get('author_matcher', {})
            import_dir = am.get('neo4j_import_dir', '')
            if not import_dir:
                am_paths = am.get('paths', {})
                if isinstance(am_paths, dict):
                    import_dir = am_paths.get('neo4j_import_dir', '')
            self._set_text("author_matcher.paths.neo4j_import_dir", import_dir or '')

            # 作者匹配
            self._set_text("author_matcher.name_column",
                           am.get('name_column', '导师姓名'))

            # 情报分析
            analytics = self.config.get('analytics', {})
            self._set_int("analytics.concept_clusters", analytics.get('concept_clusters', 25))
            self._set_check("analytics.use_llm_labels", analytics.get('use_llm_labels', True))

        except Exception as e:
            QMessageBox.warning(self, "配置加载失败", f"无法读取配置文件: {e}")

    def save_config(self):
        """将 GUI 控件中的值写回 config.yaml"""
        # 机构
        if 'institution' not in self.config:
            self.config['institution'] = {}
        inst = self.config['institution']
        inst['target_id'] = self._get_text("institution.target_id")
        inst['email'] = self._get_text("institution.email")
        inst['start_year'] = self._get_int("institution.start_year")
        end_val = self._get_int("institution.end_year")
        inst['end_year'] = end_val if end_val > 0 else None
        inst['fallback_keywords'] = [
            line.strip() for line in self._get_text("institution.fallback_keywords").split('\n')
            if line.strip()
        ]

        # 路径
        if 'paths' not in self.config:
            self.config['paths'] = {}
        paths = self.config['paths']
        for key in ["data_u1_raw", "data_u1_5_tagged", "data_u2_cleaned",
                    "data_u2_unique", "data_u2_5_nlp", "data_u3_final",
                    "input_author_excel", "output_author_excel",
                    "excel_aff_mapping", "excel_con_mapping",
                    "excel_aff_mapping_ai", "excel_con_mapping_ai"]:
            paths[key] = self._get_text(f"paths.{key}")

        # NLP
        if 'nlp' not in self.config:
            self.config['nlp'] = {}
        self.config['nlp']['target_aff_clusters'] = self._get_int("nlp.target_aff_clusters")

        # LLM
        if 'llm_assistant' not in self.config:
            self.config['llm_assistant'] = {}
        llm = self.config['llm_assistant']
        llm['enabled'] = self._get_check("llm_assistant.enabled")
        llm['api_url'] = self._get_text("llm_assistant.api_url")
        llm['concept_target_fields'] = self._get_text("llm_assistant.concept_target_fields")
        llm['affiliation_system_prompt'] = self._get_text("llm_assistant.affiliation_system_prompt")

        # 数据库
        if 'database' not in self.config:
            self.config['database'] = {}
        db = self.config['database']
        db['uri'] = self._get_text("database.uri")
        db['user'] = self._get_text("database.user")
        db['password'] = self._get_text("database.password")

        # Neo4j import dir
        if 'author_matcher' not in self.config:
            self.config['author_matcher'] = {}
        self.config['author_matcher']['neo4j_import_dir'] = \
            self._get_text("author_matcher.paths.neo4j_import_dir")

        # 作者匹配
        self.config['author_matcher']['name_column'] = \
            self._get_text("author_matcher.name_column")

        # 情报分析
        if 'analytics' not in self.config:
            self.config['analytics'] = {}
        self.config['analytics']['concept_clusters'] = self._get_int("analytics.concept_clusters")
        self.config['analytics']['use_llm_labels'] = self._get_check("analytics.use_llm_labels")

        # 写入文件
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)

    # ================================================================
    # GUI 状态控制
    # ================================================================

    def set_running(self, running: bool):
        """切换运行/停止状态"""
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self._mode_combo.setEnabled(not running)
        if running:
            self.btn_start.setText("⚙️ 流水线运行中...")
        else:
            self.btn_start.setText("🚀 开始执行")

    def update_progress(self, pct: int, status: str = ""):
        """更新进度条"""
        self._progress.setValue(pct)
        if status:
            self._progress.setFormat(status)

    def get_selected_mode(self) -> tuple:
        """获取用户选择的运行模式 -> (stages_list, mode_name)"""
        from gui.pipeline_runner import PipelineRunner
        mode = self._mode_combo.currentData()
        if mode == "dashboard_only":
            return PipelineRunner.get_dashboard_only_stages(), "一键启动大屏"
        elif mode == "full_pipeline":
            return PipelineRunner.get_full_pipeline_stages(), "完整流水线"
        else:
            # 分步执行: 收集用户勾选的阶段
            selected = []
            for key, label in PipelineRunner.ALL_STAGES:
                cb = self._step_checkboxes.get(key)
                if cb and cb.isChecked():
                    selected.append(key)
            if not selected:
                selected = PipelineRunner.get_full_pipeline_stages()
            return selected, "分步执行"

    # ================================================================
    # 内部辅助
    # ================================================================

    def _on_mode_changed(self):
        """模式切换时显示/隐藏分步复选框"""
        mode = self._mode_combo.currentData()
        self._step_widget.setVisible(mode == "step_by_step")

    def _on_start_clicked(self):
        stages, mode = self.get_selected_mode()
        self.start_requested.emit(stages, mode)

    def _set_text(self, key: str, value):
        w = self._widgets.get(key)
        if w is None:
            return
        from PySide6.QtWidgets import QLineEdit, QTextEdit
        if isinstance(w, QLineEdit):
            w.setText(str(value) if value else '')
        elif isinstance(w, QTextEdit):
            w.setPlainText(str(value) if value else '')

    def _get_text(self, key: str) -> str:
        w = self._widgets.get(key)
        if w is None:
            return ''
        from PySide6.QtWidgets import QLineEdit, QTextEdit
        if isinstance(w, QLineEdit):
            return w.text().strip()
        elif isinstance(w, QTextEdit):
            return w.toPlainText().strip()
        return ''

    def _set_int(self, key: str, value: int):
        w = self._widgets.get(key)
        if w is not None:
            from PySide6.QtWidgets import QSpinBox
            if isinstance(w, QSpinBox):
                w.setValue(int(value))

    def _get_int(self, key: str) -> int:
        w = self._widgets.get(key)
        if w is not None:
            from PySide6.QtWidgets import QSpinBox
            if isinstance(w, QSpinBox):
                return w.value()
        return 0

    def _set_check(self, key: str, value: bool):
        w = self._widgets.get(key)
        if w is not None:
            from PySide6.QtWidgets import QCheckBox
            if isinstance(w, QCheckBox):
                w.setChecked(bool(value))

    def _get_check(self, key: str) -> bool:
        w = self._widgets.get(key)
        if w is not None:
            from PySide6.QtWidgets import QCheckBox
            if isinstance(w, QCheckBox):
                return w.isChecked()
        return False
