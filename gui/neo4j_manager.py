# gui/neo4j_manager.py
"""
Neo4j 环境管理器 — Docker 生命周期 + 连接检测

支持跨平台 (Windows/Linux/macOS) 的一键 Docker 部署,
包含 Docker 可用性检测、容器启停、连接健康检查。

关键设计:
  - 所有耗时操作都运行在 Neo4jTask(QThread) 后台线程中,
    通过 Qt 信号跨线程安全地回传进度/状态/日志。
  - 长耗时操作 (docker pull、就绪等待循环) 支持 requestInterruption(),
    shutdown() 可请求停止并等待线程结束, 避免窗口关闭后线程
    向已销毁的 QObject 发信号导致崩溃。
  - 所有 Neo4j 连接都配置了 connection_timeout (5s),
    避免在 Neo4j 不可用时无限期挂起。
"""

import os
import platform
import subprocess
import threading
import time
from PySide6.QtCore import QObject, QThread, Signal

# Neo4j 连接超时 (秒) — 合理的检测超时，避免无限等待
NEO4J_CONNECTION_TIMEOUT = 5


class Neo4jTask(QThread):
    """
    后台执行单个 Neo4j 操作的任务线程。

    信号 (与 Neo4jManager 完全一致, 便于 forward):
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

    def __init__(self, func, *args, parent=None):
        super().__init__(parent)
        self._func = func
        self._args = args

    def run(self):
        """在后台线程中执行绑定的操作函数, 传入 self 作为 reporter"""
        self._func(self, *self._args)

    def request_stop(self):
        """请求停止 (长操作应在等待循环中检查 isInterruptionRequested)"""
        self.requestInterruption()


class Neo4jManager(QObject):
    """
    Neo4j Docker 容器生命周期管理器。

    信号 (由各 Neo4jTask 转发而来):
        log_message(str)
        docker_available(bool)
        neo4j_status(bool, str)
        deploy_finished(bool, str)
        operation_progress(int, str)
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
        self._tasks = []

    # ================================================================
    # 任务调度
    # ================================================================

    def _start_task(self, func, *args):
        """创建并启动一个后台任务, 把任务信号转发到自身信号"""
        task = Neo4jTask(func, *args, parent=self)
        task.log_message.connect(self.log_message)
        task.docker_available.connect(self.docker_available)
        task.neo4j_status.connect(self.neo4j_status)
        task.deploy_finished.connect(self.deploy_finished)
        task.operation_progress.connect(self.operation_progress)
        self._tasks.append(task)
        task.finished.connect(lambda t=task: self._cleanup_task(t))
        task.start()

    def _cleanup_task(self, task):
        if task in self._tasks:
            self._tasks.remove(task)
        task.deleteLater()

    def shutdown(self):
        """请求停止所有后台任务并等待 (窗口关闭前调用)"""
        for task in list(self._tasks):
            task.request_stop()
        for task in list(self._tasks):
            if not task.wait(5000):
                task.log_message.emit("⚠️ 后台任务未能在 5 秒内停止。")

    # ================================================================
    # 公开 API (薄包装)
    # ================================================================

    def check_docker(self):
        """检测 Docker 是否安装且可用"""
        self._start_task(self._do_check_docker)

    def check_neo4j_connection(self, uri: str = "bolt://localhost:7688",
                                user: str = "neo4j", password: str = ""):
        """检查 Neo4j 是否可连接"""
        self._start_task(self._do_check_neo4j, uri, user, password)

    def deploy_neo4j(self, uri: str = "bolt://localhost:7688",
                     user: str = "neo4j", password: str = "",
                     import_dir: str = ""):
        """使用 Docker 一键部署 Neo4j"""
        self._start_task(self._do_deploy, uri, user, password, import_dir)

    def start_neo4j(self, user: str = "neo4j", password: str = ""):
        """启动已有的 Neo4j 容器"""
        self._start_task(self._do_start, user, password)

    def stop_neo4j(self):
        """停止 Neo4j 容器"""
        self._start_task(self._do_stop)

    def restart_neo4j(self, user: str = "neo4j", password: str = ""):
        """重启 Neo4j 容器"""
        self._start_task(self._do_restart, user, password)

    def remove_neo4j(self):
        """删除 Neo4j 容器 (不可逆)"""
        self._start_task(self._do_remove)

    # ================================================================
    # 内部工具
    # ================================================================

    def _make_driver(self, uri: str, user: str, password: str):
        """创建带超时配置的 Neo4j 驱动"""
        from neo4j import GraphDatabase
        return GraphDatabase.driver(
            uri, auth=(user, password),
            connection_timeout=NEO4J_CONNECTION_TIMEOUT,
            connection_acquisition_timeout=NEO4J_CONNECTION_TIMEOUT,
        )

    def _run_interruptible(self, reporter, cmd, timeout, stream_log=False):
        """运行子进程并支持中断。返回 (returncode, stdout, stderr)

        stream_log=True 时，实时把 stdout 转发到日志面板，
        同时按回车/换行两种分隔符切分，避免拉取大镜像时界面毫无反馈。
        """
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0
        )
        deadline = time.time() + timeout
        stdout_lines = []
        last_emitted = [None]

        def _read_stdout():
            """后台线程：按 \\r / \\n 切分 stdout 并转发到日志"""
            buf = b""
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                buf += chunk
                while True:
                    # 取最近的 \r 或 \n 作为行分隔符
                    idx = -1
                    for sep in (b"\r", b"\n"):
                        i = buf.find(sep)
                        if i != -1 and (idx == -1 or i < idx):
                            idx = i
                    if idx == -1:
                        break
                    line = buf[:idx].decode("utf-8", "replace").strip()
                    buf = buf[idx + 1:]
                    if not line:
                        continue
                    stdout_lines.append(line)
                    if stream_log and line != last_emitted[0]:
                        reporter.log_message.emit(line)
                        last_emitted[0] = line
            tail = buf.decode("utf-8", "replace").strip()
            if tail:
                stdout_lines.append(tail)
                if stream_log and tail != last_emitted[0]:
                    reporter.log_message.emit(tail)
                    last_emitted[0] = tail

        reader = threading.Thread(target=_read_stdout, daemon=True)
        reader.start()

        while True:
            if reporter.isInterruptionRequested():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                reader.join(timeout=2)
                return -1, "\n".join(stdout_lines), "interrupted"
            if proc.poll() is not None:
                reader.join(timeout=5)
                err = proc.stderr.read()
                return proc.returncode, "\n".join(stdout_lines), err.decode("utf-8", "replace").strip()
            if time.time() > deadline:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                reader.join(timeout=2)
                return -1, "\n".join(stdout_lines), "timeout"
            time.sleep(0.5)

    # ================================================================
    # 后台任务实现
    # ================================================================

    def _do_check_docker(self, reporter):
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True, timeout=10, text=True
            )
            if result.returncode == 0:
                reporter.log_message.emit(f"✅ Docker 已安装: {result.stdout.strip()}")
                reporter.docker_available.emit(True)
            else:
                reporter.log_message.emit("❌ Docker 命令返回错误。")
                reporter.docker_available.emit(False)
        except FileNotFoundError:
            reporter.log_message.emit("❌ 未找到 Docker。请安装 Docker Desktop。")
            reporter.log_message.emit("   下载地址: https://www.docker.com/products/docker-desktop/")
            reporter.docker_available.emit(False)
        except subprocess.TimeoutExpired:
            reporter.log_message.emit("❌ Docker 检测超时，Docker 守护进程可能未启动。")
            reporter.docker_available.emit(False)
        except Exception as e:
            reporter.log_message.emit(f"❌ Docker 检测异常: {e}")
            reporter.docker_available.emit(False)

    def _do_check_neo4j(self, reporter, uri, user, password):
        try:
            driver = self._make_driver(uri, user, password)
            with driver.session() as session:
                result = session.run("RETURN 1 as n")
                result.single()
            driver.close()
            reporter.log_message.emit(f"✅ Neo4j 连接成功: {uri}")
            reporter.neo4j_status.emit(True, "已连接")
        except Exception as e:
            reporter.log_message.emit(f"⚠️ Neo4j 未连接 ({uri}): {e}")
            reporter.neo4j_status.emit(False, "未连接")

    def _do_deploy(self, reporter, uri, user, password, import_dir):
        reporter.operation_progress.emit(10, "正在检测 Docker 环境...")

        # 1. 检测 Docker
        try:
            subprocess.run(
                ["docker", "--version"],
                capture_output=True, check=True, timeout=10
            )
        except Exception as e:
            err_msg = str(e).lower()
            reporter.log_message.emit(f"❌ Docker 不可用: {e}")
            if 'permission denied' in err_msg:
                reporter.log_message.emit("   👉 权限不足！请将当前用户加入 docker 组:")
                reporter.log_message.emit("      sudo usermod -aG docker $USER")
                reporter.log_message.emit("      然后注销重新登录即可生效。")
            else:
                reporter.log_message.emit("   请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop/")
            reporter.deploy_finished.emit(False, "Docker 权限不足" if 'permission' in err_msg else "Docker 未安装")
            return

        if reporter.isInterruptionRequested():
            reporter.deploy_finished.emit(False, "部署已取消")
            return

        reporter.operation_progress.emit(20, "正在清理旧容器...")

        # 2. 删除已有同名容器
        subprocess.run(
            ["docker", "rm", "-f", self.CONTAINER_NAME],
            capture_output=True, timeout=30
        )

        reporter.operation_progress.emit(30, "正在拉取 Neo4j 镜像 (首次需下载)...")

        # 3. 拉取镜像 (可中断)
        pull_code, pull_out, pull_err = self._run_interruptible(
            reporter, ["docker", "pull", self.IMAGE_NAME], timeout=300, stream_log=True
        )
        if reporter.isInterruptionRequested():
            reporter.log_message.emit("⏹ 镜像拉取已取消。")
            reporter.deploy_finished.emit(False, "部署已取消")
            return
        if pull_code != 0:
            reporter.log_message.emit(f"❌ 镜像拉取失败: {pull_err}")
            reporter.deploy_finished.emit(False, "镜像拉取失败")
            return

        reporter.operation_progress.emit(50, "正在创建 Neo4j 容器...")

        # 4. 解析端口
        if ":" in uri:
            bolt_port = uri.split(":")[-1]
        else:
            bolt_port = "7688"
        http_port = str(int(bolt_port) + 1)  # HTTP 端口通常是 bolt+1

        # 5. 准备导入目录挂载
        abs_import = os.path.abspath(import_dir) if import_dir else os.path.abspath("./data/import")
        try:
            os.makedirs(abs_import, exist_ok=True)
        except OSError as e:
            reporter.log_message.emit(f"⚠️ 无法创建导入目录 {abs_import}: {e}")
            reporter.log_message.emit("   回退到项目内 ./data/import")
            abs_import = os.path.abspath("./data/import")
            os.makedirs(abs_import, exist_ok=True)
        if self._os_type == "Windows":
            abs_import = abs_import.replace("\\", "/")

        reporter.log_message.emit(f"   -> Bolt 端口: {bolt_port}")
        reporter.log_message.emit(f"   -> HTTP 端口: {http_port}")
        reporter.log_message.emit(f"   -> 挂载目录: {abs_import}")

        # 6. 启动容器
        docker_cmd = [
            "docker", "run", "-d",
            "--name", self.CONTAINER_NAME,
            "-p", f"{bolt_port}:7687",
            "-p", f"{http_port}:7474",
            "-e", f"NEO4J_AUTH={user}/{password}",
            "-e", "NEO4J_PLUGINS=[\"apoc\"]",
            "-e", "NEO4J_server_directories_import=/import",
            "-v", f"{abs_import}:/import",
            "--restart", "unless-stopped",
            self.IMAGE_NAME,
        ]

        run_result = subprocess.run(
            docker_cmd,
            capture_output=True, text=True, timeout=60
        )

        if run_result.returncode != 0:
            reporter.log_message.emit(f"❌ 容器启动失败: {run_result.stderr}")
            reporter.deploy_finished.emit(False, "容器启动失败")
            return

        container_id = run_result.stdout.strip()[:12]
        reporter.log_message.emit(f"   -> 容器已启动: {container_id}")

        reporter.operation_progress.emit(70, "等待 Neo4j 初始化...")

        # 7. 等待 Neo4j 就绪 (最多 60 秒, 可中断)
        self._owned_by_app = True
        deadline = time.time() + 60
        ready = False

        while time.time() < deadline:
            if reporter.isInterruptionRequested():
                reporter.log_message.emit("⏹ 部署等待已取消 (容器可能仍在初始化)。")
                reporter.deploy_finished.emit(True, "容器已启动，等待数据库初始化中...")
                return
            try:
                test_driver = self._make_driver(
                    f"bolt://localhost:{bolt_port}", user, password
                )
                with test_driver.session() as session:
                    session.run("RETURN 1")
                test_driver.close()
                ready = True
                break
            except Exception:
                time.sleep(3)
                reporter.operation_progress.emit(
                    min(90, 70 + int((time.time() - (deadline - 60)) / 60 * 20)),
                    "等待 Neo4j 就绪..."
                )

        reporter.operation_progress.emit(100, "部署完成")

        if ready:
            reporter.log_message.emit(f"✅ Neo4j 部署成功！Bolt: bolt://localhost:{bolt_port}")
            reporter.log_message.emit(f"   HTTP 控制台: http://localhost:{http_port}")
            reporter.deploy_finished.emit(True, f"已就绪 — bolt://localhost:{bolt_port}")
            reporter.neo4j_status.emit(True, "已连接")
        else:
            reporter.log_message.emit("⚠️ 容器已启动但 Neo4j 初始化超时，请稍后重试连接。")
            reporter.deploy_finished.emit(True, "容器已启动，等待数据库初始化中...")

    def _do_start(self, reporter, user, password):
        # 检查容器是否存在
        check = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={self.CONTAINER_NAME}",
             "--format", "{{.Status}}"],
            capture_output=True, text=True, timeout=10
        )
        status = check.stdout.strip()
        if not status:
            reporter.log_message.emit(f"⚠️ 容器 {self.CONTAINER_NAME} 不存在，请先点击「一键部署」。")
            return
        if status.startswith("Up"):
            reporter.log_message.emit(f"ℹ️ Neo4j 容器已在运行中 ({status})")
            reporter.neo4j_status.emit(True, "已运行")
        else:
            subprocess.run(["docker", "start", self.CONTAINER_NAME],
                           capture_output=True, timeout=30)
            reporter.log_message.emit("▶ Neo4j 容器已启动，等待就绪...")
            self._owned_by_app = True
            # 等待连接 (带超时, 可中断)
            deadline = time.time() + 30
            while time.time() < deadline:
                if reporter.isInterruptionRequested():
                    reporter.neo4j_status.emit(True, "启动中")
                    return
                try:
                    d = self._make_driver("bolt://localhost:7688", user, password)
                    with d.session() as s:
                        s.run("RETURN 1")
                    d.close()
                    reporter.log_message.emit("✅ Neo4j 已就绪")
                    reporter.neo4j_status.emit(True, "已连接")
                    return
                except Exception:
                    time.sleep(2)
            reporter.log_message.emit("⚠️ 容器已启动，Neo4j 初始化中...")
            reporter.neo4j_status.emit(True, "启动中")

    def _do_stop(self, reporter):
        check = subprocess.run(
            ["docker", "ps", "--filter", f"name={self.CONTAINER_NAME}",
             "--format", "{{.ID}}"],
            capture_output=True, text=True, timeout=10
        )
        if not check.stdout.strip():
            reporter.log_message.emit("ℹ️ Neo4j 容器未在运行。")
            reporter.neo4j_status.emit(False, "未运行")
            return
        subprocess.run(["docker", "stop", self.CONTAINER_NAME],
                       capture_output=True, timeout=30)
        reporter.log_message.emit("🛑 Neo4j 容器已停止。")
        reporter.neo4j_status.emit(False, "已停止")

    def _do_restart(self, reporter, user, password):
        reporter.log_message.emit("🔄 正在重启 Neo4j 容器...")
        subprocess.run(["docker", "restart", self.CONTAINER_NAME],
                       capture_output=True, timeout=30)
        reporter.log_message.emit("✅ 容器已重启，等待就绪...")
        time.sleep(5)
        if reporter.isInterruptionRequested():
            reporter.neo4j_status.emit(False, "启动中")
            return
        self._owned_by_app = True
        # 快速连接检查 (带超时)
        try:
            d = self._make_driver("bolt://localhost:7688", user, password)
            with d.session() as s:
                s.run("RETURN 1")
            d.close()
            reporter.log_message.emit("✅ Neo4j 已就绪")
            reporter.neo4j_status.emit(True, "已连接")
        except Exception:
            reporter.log_message.emit("⚠️ Neo4j 正在启动，请稍后点击「测试连接」")
            reporter.neo4j_status.emit(False, "启动中")

    def _do_remove(self, reporter):
        result = subprocess.run(
            ["docker", "rm", "-f", self.CONTAINER_NAME],
            capture_output=True, text=True, timeout=30
        )
        reporter.log_message.emit(f"🗑 Neo4j 容器已删除: {result.stdout.strip()}")
        reporter.neo4j_status.emit(False, "已删除")
        self._owned_by_app = False

    @property
    def is_owned_by_app(self) -> bool:
        return self._owned_by_app
