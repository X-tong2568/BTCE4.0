import asyncio
import time
from functools import wraps
from typing import Type, Tuple
from logger_config import logger

class RetryConfig:
    def __init__(self, max_attempts: int = 3, delay: float = 5,
                 exceptions: Tuple[Type[Exception], ...] = (Exception,)):
        self.max_attempts = max_attempts
        self.delay = delay
        self.exceptions = exceptions

def async_retry(config: RetryConfig):
    """异步重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(config.max_attempts):
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"✅ {func.__name__} 在第 {attempt + 1} 次重试后成功")
                    return result
                except config.exceptions as e:
                    last_exception = e
                    if attempt < config.max_attempts - 1:
                        logger.warning(
                            f"🔄 {func.__name__} 第 {attempt + 1} 次失败: {str(e)}. "
                            f"{config.delay}秒后重试..."
                        )
                        await asyncio.sleep(config.delay)
                    else:
                        logger.error(f"❌ {func.__name__} 重试 {config.max_attempts} 次后仍失败")
            raise last_exception
        return wrapper
    return decorator

# 预定义的重试配置
NETWORK_RETRY_CONFIG = RetryConfig(max_attempts=3, delay=5, exceptions=(TimeoutError, ConnectionError))
BROWSER_RETRY_CONFIG = RetryConfig(max_attempts=2, delay=10, exceptions=(Exception,))