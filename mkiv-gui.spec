# -*- mode: python ; coding: utf-8 -*-
# MKIV Academic Intelligence Graph Engine — PyInstaller Spec
# Build: pyinstaller mkiv-gui.spec

import sys, os
from pathlib import Path

block_cipher = None

# 项目根目录 (SPECPATH 由 PyInstaller 提供)
PROJECT_ROOT = Path(SPECPATH).parent if 'SPECPATH' in dir() else Path(os.path.abspath('.'))

a = Analysis(
    ['gui_main.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        ('config/config.yaml', 'config'),
    ],
    hiddenimports=[
        # Qt WebEngine (CRITICAL: must be explicit)
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        # Pipeline
        'pipelines.data_pipeline',
        'pipelines.name_pipeline',
        # Core
        'core.crawler',
        'core.author_matcher',
        'core.cleaner',
        'core.analyzer',
        'core.assembler',
        'core.llm_labeler',
        'core.name_processor',
        'core.db_importer',
        'core.visualizer',
        # Utils
        'utils.file_handler',
        # GUI
        'gui.main_window',
        'gui.parameter_panel',
        'gui.dashboard_panel',
        'gui.pipeline_runner',
        'gui.neo4j_manager',
        'gui.log_handler',
        'gui.help_texts',
        'gui.dark_theme',
        'gui.startup_wizard',
        'gui.widgets',
        # ML
        'sentence_transformers',
        'sklearn.cluster',
        'sklearn.cluster._agglomerative',
        # Other
        'neo4j',
        'pypinyin',
        'openpyxl',
        'yaml',
        'requests',
        'pandas',
        'tqdm',
        'uvicorn',
        'fastapi',
        'urllib3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'numpy.tests',
        'pandas.tests',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MKIV_Academic_Graph',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add custom .ico file to gui/resources/
)

if sys.platform == 'win32':
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='MKIV_Academic_Graph',
    )
