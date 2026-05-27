# status_monitor.py
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from logger_config import logger
from email_utils import send_email
from config_email import STATUS_MONITOR_EMAILS
from config import (
    UP_NAME,
    STATUS_MONITOR_INTERVAL,
    NO_UPDATE_ALERT_HOURS,
)

# ===== 可调参数：重复提醒间隔（小时）=====
ALERT_REPEAT_INTERVAL_HOURS = 60


class StatusMonitor:
    """
    状态监控器：检测长时间无更新情况

    设计语义说明：
    - 程序启动（包括服务器每日 02:30 重启）视为一次“人工确认”
    - 超过 NO_UPDATE_ALERT_HOURS 未更新 → 首次告警
    - 若告警后未人工处理 → 按 ALERT_REPEAT_INTERVAL_HOURS 周期重复提醒
    - 若人工重启 / 修改配置 → 计时重新开始
    """

    def __init__(self):
        self.status_file = Path("monitor_status.json")
        self.no_update_alert_hours = NO_UPDATE_ALERT_HOURS
        self.monitor_interval = STATUS_MONITOR_INTERVAL

        self.status_data = self._load_status()

        # ⭐ 程序启动即视为一次人工确认
        self._acknowledge_alert(on_startup=True)

    # ------------------------------------------------------------------
    # 状态加载 / 保存
    # ------------------------------------------------------------------

    def _load_status(self):
        current_time = time.time()

        default_status = {
            "last_change_time": current_time,
            "last_alert_time": None,          # 从未提醒
            "total_changes": 0,
            "start_time": current_time,
            "alert_acknowledged": True,       # 启动即确认
        }

        if self.status_file.exists():
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 补齐缺失字段
                for key, value in default_status.items():
                    if key not in data:
                        data[key] = value

                return data

            except Exception as e:
                logger.error(f"❌ 加载状态文件失败，使用默认状态: {e}")

        return default_status

    def _save_status(self):
        try:
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump(self.status_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存状态文件失败: {e}")

    # ------------------------------------------------------------------
    # 状态更新
    # ------------------------------------------------------------------

    def record_change(self):
        """记录检测到更新（意味着异常解除）"""
        self.status_data["last_change_time"] = time.time()
        self.status_data["total_changes"] += 1

        # 有更新即自动确认告警
        self._acknowledge_alert()

        logger.info("✅ 已记录变化时间戳")
        self._save_status()

    def _acknowledge_alert(self, on_startup=False):
        """
        人工确认告警：
        - 程序启动
        - 人工重启
        - 检测到新变化
        """
        self.status_data["alert_acknowledged"] = True
        self.status_data["last_alert_time"] = None

        if on_startup:
            logger.info("🔁 程序启动：视为一次人工确认，告警状态已重置")

        self._save_status()

    # ------------------------------------------------------------------
    # 告警检查逻辑
    # ------------------------------------------------------------------

    async def check_no_update_alert(self):
        """检查是否需要发送无更新提醒"""

        current_time = time.time()
        last_change_time = self.status_data["last_change_time"]
        last_alert_time = self.status_data["last_alert_time"]
        acknowledged = self.status_data["alert_acknowledged"]

        hours_without_update = (current_time - last_change_time) / 3600

        # 未超过阈值，不可能告警
        if hours_without_update < self.no_update_alert_hours:
            return False

        # 已人工确认过，但尚未达到再次确认的条件
        if acknowledged:
            self.status_data["alert_acknowledged"] = False
            self._save_status()

        # 是否允许发送告警
        allow_alert = False

        if last_alert_time is None:
            # 首次告警
            allow_alert = True
        else:
            hours_since_last_alert = (current_time - last_alert_time) / 3600
            if hours_since_last_alert >= ALERT_REPEAT_INTERVAL_HOURS:
                allow_alert = True

        if not allow_alert:
            return False

        logger.warning(
            f"⚠️ 已 {hours_without_update:.1f} 小时未检测到更新，发送提醒邮件"
        )

        success = await self._send_no_update_alert(hours_without_update)

        if success:
            self.status_data["last_alert_time"] = current_time
            self._save_status()
            return True

        return False

    # ------------------------------------------------------------------
    # 邮件发送
    # ------------------------------------------------------------------

    async def _send_no_update_alert(self, hours_without_update):
        try:
            current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            hours_int = int(hours_without_update)

            subject = f"【{UP_NAME}监控提醒】长时间未检测到置顶评论更新"

            content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>监控提醒</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; }}
.alert {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; }}
.info {{ background-color: #d1ecf1; border: 1px solid #bee5eb; padding: 10px; margin-top: 10px; border-radius: 5px; }}
</style>
</head>
<body>

<div class="alert">
<h2>⚠️ 监控系统提醒</h2>
<p>已超过 <strong>{hours_int} 小时</strong> 未检测到动态置顶评论更新。</p>
</div>

<div class="info">
<h3>📊 监控信息</h3>
<p>最后更新时间：{datetime.fromtimestamp(self.status_data["last_change_time"]).strftime("%Y-%m-%d %H:%M:%S")}</p>
<p>累计变化次数：{self.status_data["total_changes"]}</p>
<p>系统运行时长：{self._format_runtime()}</p>
<p>当前系统时间：{current_time_str}</p>
</div>

<div class="info">
<h3>🔍 建议操作</h3>
<ol>
<li>确认 UP 主近期是否确实无更新</li>
<li>检查动态链接是否仍有效</li>
<li>如已人工确认无异常，可忽略本提醒</li>
<li>如修改配置或修复问题，请重启程序</li>
</ol>
</div>

</body>
</html>
"""

            success = await asyncio.to_thread(
                send_email,
                subject=subject,
                content=content,
                to_emails=STATUS_MONITOR_EMAILS,
            )

            if success:
                logger.info("✅ 无更新提醒邮件发送成功")
            else:
                logger.error("❌ 无更新提醒邮件发送失败")

            return success

        except Exception as e:
            logger.error(f"❌ 发送无更新提醒失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _format_runtime(self):
        runtime_seconds = time.time() - self.status_data["start_time"]
        days = int(runtime_seconds // 86400)
        hours = int((runtime_seconds % 86400) // 3600)
        return f"{days}天{hours}小时"

    def get_status_info(self):
        current_time = time.time()
        hours_without_update = (current_time - self.status_data["last_change_time"]) / 3600

        if self.status_data["last_alert_time"] is None:
            alert_display = "从未告警"
        else:
            hours_since_last_alert = (
                current_time - self.status_data["last_alert_time"]
            ) / 3600
            alert_display = f"{hours_since_last_alert:.1f}小时前"

        return {
            "最后更新": datetime.fromtimestamp(self.status_data["last_change_time"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "无更新时长": f"{hours_without_update:.1f}小时",
            "总变化次数": self.status_data["total_changes"],
            "累计运行时长": self._format_runtime(),
            "上次告警": alert_display,
        }


# 全局实例
status_monitor = StatusMonitor()
