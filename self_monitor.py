# self_monitor.py
import time
from datetime import datetime
from logger_config import logger
from config import LIVE_FAILURE_THRESHOLD, LIVE_SUCCESS_RATE_THRESHOLD


class FailureCounter:
    """失败计数器（用于自监控）"""

    def __init__(self, module_name: str, failure_threshold: int = 10, success_rate_threshold: float = 0.8):
        self.module_name = module_name
        self.failure_threshold = failure_threshold
        self.success_rate_threshold = success_rate_threshold

        self.success_count = 0
        self.failure_count = 0
        self.consecutive_failures = 0
        self.last_reset_time = time.time()
        self.failure_history = []

    def record_success(self):
        """记录成功"""
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_reset_time = time.time()

    def record_failure(self, error_msg: str = ""):
        """记录失败"""
        self.failure_count += 1
        self.consecutive_failures += 1

        # 记录失败历史（最近10次）
        failure_record = {
            'timestamp': time.time(),
            'time_str': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': error_msg
        }
        self.failure_history.append(failure_record)
        self.failure_history = self.failure_history[-10:]  # 只保留最近10次

    def should_alert(self) -> bool:
        """检查是否需要告警"""
        total_attempts = self.success_count + self.failure_count

        # P1告警：连续失败达到阈值
        if self.consecutive_failures >= self.failure_threshold:
            return True

        # P2告警：成功率低于阈值（至少有10次尝试）
        if total_attempts >= 10:
            success_rate = self.success_count / total_attempts
            if success_rate < self.success_rate_threshold:
                return True

        return False

    def get_stats(self) -> dict:
        """获取统计信息"""
        total_attempts = self.success_count + self.failure_count
        success_rate = self.success_count / total_attempts if total_attempts > 0 else 0

        return {
            'module': self.module_name,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'consecutive_failures': self.consecutive_failures,
            'success_rate': f"{success_rate:.2%}",
            'total_attempts': total_attempts,
            'last_reset': datetime.fromtimestamp(self.last_reset_time).strftime('%Y-%m-%d %H:%M:%S'),
            'should_alert': self.should_alert()
        }

    def reset(self):
        """重置计数器"""
        self.success_count = 0
        self.failure_count = 0
        self.consecutive_failures = 0
        self.last_reset_time = time.time()
        self.failure_history = []


# 创建直播监控的失败计数器实例
live_failure_counter = FailureCounter(
    'live_monitor',
    failure_threshold=LIVE_FAILURE_THRESHOLD,
    success_rate_threshold=LIVE_SUCCESS_RATE_THRESHOLD
)