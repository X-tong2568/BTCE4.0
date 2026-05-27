import logging
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import time
import glob
import os
from datetime import datetime, timedelta
from config import LOG_DIR, MAX_LOG_SIZE_MB, LOG_BACKUP_COUNT


def cleanup_old_logs():
    """清理过期的日志文件"""
    try:
        # 更精确的日志文件模式
        log_patterns = [
            "monitor.log.*",  # 匹配 monitor.log.1, monitor.log.2 等
            "error.log.*",  # 匹配 error.log.1, error.log.2 等
            "performance.log.*",  # 匹配所有 performance.log.*
            "combined__*",  # 匹配 combined__2025-12-15 23:12:49
            "out__*",  # 匹配 out__2025-12-15 23:12:49
            "err__*",  # 匹配 err__2025-12-15 23:12:49
            "combined.log",  # 基础文件
            "out.log",  # 基础文件
            "err.log"  # 基础文件
        ]

        deleted_files = []
        current_time = time.time()

        for pattern in log_patterns:
            # 使用 glob 递归查找匹配的文件
            for log_file in LOG_DIR.glob(pattern):
                try:
                    # 跳过符号链接和目录
                    if not log_file.is_file():
                        continue

                    # 计算文件修改时间（天）
                    file_age = current_time - log_file.stat().st_mtime
                    days_old = file_age / (24 * 3600)

                    # 设置保留天数（这里设置为3天）
                    retention_days = 3

                    if days_old > retention_days:
                        log_file.unlink()
                        deleted_files.append(f"{log_file.name} ({days_old:.1f}天前)")
                        print(f"🗑️ 已删除: {log_file.name} ({days_old:.1f}天前)")
                except Exception as e:
                    print(f"❌ 删除文件 {log_file} 失败: {e}")

        if deleted_files:
            print(f"✅ 总共清理了 {len(deleted_files)} 个旧日志文件")
            for file_info in deleted_files:
                print(f"   - {file_info}")
        else:
            print("ℹ️ 没有找到需要清理的旧日志文件")

    except Exception as e:
        print(f"❌ 日志清理过程出错: {e}")


def cleanup_old_performance_logs():
    """专门清理按时间轮转的性能日志"""
    try:
        # 查找所有 performance.log.* 文件
        perf_patterns = [
            "performance.log.*",  # 匹配带日期时间的文件
        ]

        deleted_files = []
        current_time = time.time()
        retention_days = 3  # 保留3天

        for pattern in perf_patterns:
            for log_file in LOG_DIR.glob(pattern):
                try:
                    # 跳过目录
                    if not log_file.is_file():
                        continue

                    # 检查是否已经是轮转文件（不删除当前活跃的 performance.log）
                    if log_file.name == "performance.log":
                        continue

                    # 计算文件年龄
                    file_age = current_time - log_file.stat().st_mtime
                    days_old = file_age / (24 * 3600)

                    if days_old > retention_days:
                        log_file.unlink()
                        deleted_files.append(f"{log_file.name} ({days_old:.1f}天前)")
                        print(f"🗑️ 删除性能日志: {log_file.name}")

                except Exception as e:
                    print(f"❌ 删除性能日志 {log_file} 失败: {e}")

        return deleted_files

    except Exception as e:
        print(f"❌ 性能日志清理失败: {e}")
        return []


def setup_logging():
    """配置日志系统"""
    # 先清理旧日志
    print("开始清理旧日志文件...")
    cleanup_old_logs()

    # 专门清理性能日志
    print("清理旧性能日志文件...")
    perf_deleted = cleanup_old_performance_logs()
    if perf_deleted:
        print(f"✅ 清理了 {len(perf_deleted)} 个性能日志文件")

    # 确保日志目录存在
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 创建logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 清除已有的handler
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # 创建formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 主日志文件 - 按大小轮转
    log_file = LOG_DIR / "monitor.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 错误日志单独记录
    error_handler = RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    # 性能日志 - 按天轮转
    # 注意：TimedRotatingFileHandler 会自动删除旧文件
    perf_handler = TimedRotatingFileHandler(
        LOG_DIR / "performance.log",
        when='midnight',  # 每天午夜轮转
        interval=1,
        backupCount=3,  # 保留3天的备份
        encoding='utf-8'
    )
    perf_handler.setLevel(logging.INFO)
    perf_handler.setFormatter(formatter)

    # 设置文件名后缀格式
    perf_handler.suffix = "%Y-%m-%d"
    logger.addHandler(perf_handler)

    logger.info("✅ 日志系统初始化完成")
    logger.info(f"📁 日志目录: {LOG_DIR}")

    return logger


# # 独立的清理函数，可以手动调用
# def cleanup_logs_now(retention_days=3):
#     """立即执行日志清理"""
#     print(f"🧹 开始清理超过 {retention_days} 天的日志文件...")

#     # 临时修改保留天数
#     import cleanup_old_logs  # 如果需要，可以创建一个模块变量

#     # 重新运行清理
#     cleanup_old_logs()

#     print("🧹 日志清理完成")


# 创建全局logger实例
logger = logging.getLogger('BiliMonitor')

if __name__ == "__main__":
    # 可以直接运行此脚本来测试清理功能
    print("=== 测试日志清理功能 ===")
    cleanup_old_logs()