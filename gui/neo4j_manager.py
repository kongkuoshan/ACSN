# gui/neo4j_manager.py
"""
Neo4j 环境管理器 — Docker 生命周期 + 连接检测

支持跨平台 (Windows/Linux/macOS) 的一键 Docker 部署,
包含 Docker 可用性检测、容器启停、连接健康检查。
"""

import os
import platform
import subprocess
import time
import threading
from PySide6.QtCore import QObject, Signal


class Neo4jManager(QObject):
    """
    Neo4j Docker 容器生命周期管理器。

    信号:
        log_message(str): 实时日志
        docker_available(bool): Docker 是否可用
        neo4j_status(bool, str): Neo4j 连接状态
        deploy_finished(bool, str): 部署完成通知
        operation_progress(int, str): 操作进度
    """

    log_message = Signal(str)
    docker_available = Signal(bool)
    neo4j_status = Signal(bool, str)
    deploy_finished = Signal(bool, str)
    operation_progress = Signal(int, str)

    CONTAINER_NAME = "mkiv_neo4j"
    IMAGE_NAME = "neo4j:5-community"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._owned_by_app = False
        self._os_type = platform.system()

    # ================================================================
    # Docker 检测
    # ================================================================

    def check_docker(self):
        """检测 Docker 是否安装且可用 (在后台线程中运行)"""
        def _check():
            try:
                result = subprocess.run(
                    ["docker", "--version"],
                    capture_output=True, timeout=10, text=True
                )
                if result.returncode == 0:
                    self.log_message.emit(f"✅ Docker 已安装: {result.stdout.strip()}")
                    self.docker_available.emit(True)
                else:
                    self.log_message.emit("❌ Docker 命令返回错误。")
                    self.docker_available.emit(False)
            except FileNotFoundError:
                self.log_message.emit("❌ 未找到 Docker。请安装 Docker Desktop。")
                self.log_message.emit("   下载地址: https://www.docker.com/products/docker-desktop/")
                self.docker_available.emit(False)
            except subprocess.TimeoutExpired:
                self.log_message.emit("❌ Docker 检测超时，Docker 守护进程可能未启动。")
                self.docker_available.emit(False)
            except Exception as e:
                self.log_message.emit(f"❌ Docker 检测异常: {e}")
                self.docker_available.emit(False)

        threading.Thread(target=_check, daemon=True).start()

    # ================================================================
    # Neo4j 连接检查
    # ================================================================

    def check_neo4j_connection(self, uri: str = "bolt://localhost:7688",
                                user: str = "neo4j", password: str = "12345678"):
        """检查 Neo4j 是否可连接"""
        def _check():
            try:
                from neo4j import GraphDatabase
                driver = GraphDatabase.driver(uri, auth=(user, password))
                with driver.session() as session:
                    result = session.run("RETURN 1 as n")
                    result.single()
                driver.close()
                self.log_message.emit(f"✅ Neo4j 连接成功: {uri}")
                self.neo4j_status.emit(True, "已连接")
            except Exception as e:
                self.log_message.emit(f"⚠️ Neo4j 未连接 ({uri}): {e}")
                self.neo4j_status.emit(False, "未连接")

        threading.Thread(target=_check, daemon=True).start()

    # ================================================================
    # Docker 部署
    # ================================================================

    def deploy_neo4j(self, uri: str = "bolt://localhost:7688",
                     user: str = "neo4j", password: str = "12345678",
                     import_dir: str = ""):
        """
        使用 Docker 一键部署 Neo4j。

        参数:
            uri: Bolt 连接地址 (如 bolt://localhost:7688)
            user: 数据库用户名
            password: 数据库密码
            import_dir: CSV 导入目录 (宿主机路径)
        """
        def _deploy():
            self.operation_progress.emit(10, "正在检测 Docker 环境...")

            # 1. 检测 Docker
            try:
                subprocess.run(
                    ["docker", "--version"],
                    capture_output=True, check=True, timeout=10
                )
            except Exception as e:
                self.log_message.emit(f"❌ Docker 不可用: {e}")
                self.log_message.emit("   请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop/")
                self.deploy_finished.emit(False, "Docker 未安装")
                return

            self.operation_progress.emit(20, "正在清理旧容器...")

            # 2. 删除已有同名容器
            subprocess.run(
                ["docker", "rm", "-f", self.CONTAINER_NAME],
                capture_output=True, timeout=30
            )

            self.operation_progress.emit(30, "正在拉取 Neo4j 镜像 (首次需下载)...")

            # 3. 拉取镜像
            pull_result = subprocess.run(
                ["docker", "pull", self.IMAGE_NAME],
                capture_output=True, text=True, timeout=300
            )
            if pull_result.returncode != 0:
                self.log_message.emit(f"❌ 镜像拉取失败: {pull_result.stderr}")
                self.deploy_finished.emit(False, "镜像拉取失败")
                return

            self.operation_progress.emit(50, "正在创建 Neo4j 容器...")

            # 4. 解析端口
            if ":" in uri:
                bolt_port = uri.split(":")[-1]
            else:
                bolt_port = "7688"
            http_port = str(int(bolt_port) + 1)  # HTTP 端口通常是 bolt+1

            # 5. 准备导入目录挂载
            abs_import = os.path.abspath(import_dir) if import_dir else os.path.abspath("./data/import")
            os.makedirs(abs_import, exist_ok=True)
            # 跨平台路径规范化
            if self._os_type == "Windows":
                abs_import = abs_import.replace("\\", "/")

            self.log_message.emit(f"   -> Bolt 端口: {bolt_port}")
            self.log_message.emit(f"   -> HTTP 端口: {http_port}")
            self.log_message.emit(f"   -> 挂载目录: {abs_import}")

            # 6. 启动容器
            docker_cmd = [
                "docker", "run", "-d",
                "--name", self.CONTAINER_NAME,
                "-p", f"{bolt_port}:7687",
                "-p", f"{http_port}:7474",
                "-e", f"NEO4J_AUTH={user}/{password}",
                "-e", "NEO4J_PLUGINS=[\"apoc\"]",
                "-v", f"{abs_import}:/var/lib/neo4j/import",
                "--restart", "unless-stopped",
                self.IMAGE_NAME,
            ]

            run_result = subprocess.run(
                docker_cmd,
                capture_output=True, text=True, timeout=60
            )

            if run_result.returncode != 0:
                self.log_message.emit(f"❌ 容器启动失败: {run_result.stderr}")
                self.deploy_finished.emit(False, "容器启动失败")
                return

            container_id = run_result.stdout.strip()[:12]
            self.log_message.emit(f"   -> 容器已启动: {container_id}")

            self.operation_progress.emit(70, "等待 Neo4j 初始化...")

            # 7. 等待 Neo4j 就绪 (最多 60 秒)
            self._owned_by_app = True
            deadline = time.time() + 60
            ready = False

            while time.time() < deadline:
                try:
                    from neo4j import GraphDatabase
                    test_driver = GraphDatabase.driver(
                        f"bolt://localhost:{bolt_port}",
                        auth=(user, password)
                    )
                    with test_driver.session() as session:
                        session.run("RETURN 1")
                    test_driver.close()
                    ready = True
                    break
                except Exception:
                    time.sleep(3)
                    self.operation_progress.emit(
                        min(90, 70 + int((time.time() - (deadline - 60)) / 60 * 20)),
                        "等待 Neo4j 就绪..."
                    )

            self.operation_progress.emit(100, "部署完成")

            if ready:
                self.log_message.emit(f"✅ Neo4j 部署成功！Bolt: bolt://localhost:{bolt_port}")
                self.log_message.emit(f"   HTTP 控制台: http://localhost:{http_port}")
                self.deploy_finished.emit(True, f"已就绪 — bolt://localhost:{bolt_port}")
                self.neo4j_status.emit(True, "已连接")
            else:
                self.log_message.emit("⚠️ 容器已启动但 Neo4j 初始化超时，请稍后重试连接。")
                self.deploy_finished.emit(True, "容器已启动，等待数据库初始化中...")

        threading.Thread(target=_deploy, daemon=True).start()

    # ================================================================
    # 容器管理
    # ================================================================

    def stop_neo4j(self):
        """停止 Neo4j 容器"""
        if not self._owned_by_app:
            self.log_message.emit("ℹ️ 容器非本程序创建，不自动停止。")
            return

        def _stop():
            subprocess.run(
                ["docker", "stop", self.CONTAINER_NAME],
                capture_output=True, timeout=30
            )
            self.log_message.emit("🛑 Neo4j 容器已停止。")
            self.neo4j_status.emit(False, "已停止")

        threading.Thread(target=_stop, daemon=True).start()

    def remove_neo4j(self):
        """删除 Neo4j 容器"""
        def _remove():
            result = subprocess.run(
                ["docker", "rm", "-f", self.CONTAINER_NAME],
                capture_output=True, text=True, timeout=30
            )
            self.log_message.emit(f"🗑 Neo4j 容器已删除: {result.stdout.strip()}")
            self.neo4j_status.emit(False, "已删除")

        threading.Thread(target=_remove, daemon=True).start()

    @property
    def is_owned_by_app(self) -> bool:
        return self._owned_by_app
