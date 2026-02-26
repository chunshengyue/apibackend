import time
from collections import defaultdict

# 简单的内存限流器
# 记录每个 DeviceID 的请求时间戳列表
# { "device_id": [171001, 171002, ...] }
_requests = defaultdict(list)

# 限制规则：1分钟内最多 20 次 (你可以改)
LIMIT_WINDOW = 60
MAX_REQUESTS = 20


def check_limit(device_id: str) -> bool:
    if not device_id:
        return True  # 如果没有 ID，默认放行或者拦截，看你策略，这里放行方便测试

    now = time.time()
    history = _requests[device_id]

    # 1. 清理过期记录 (超过窗口期的)
    # 列表推导式过滤，只保留窗口内的
    valid_history = [t for t in history if t > now - LIMIT_WINDOW]
    _requests[device_id] = valid_history

    # 2. 检查次数
    if len(valid_history) >= MAX_REQUESTS:
        return False  # 超限

    # 3. 记录本次请求
    _requests[device_id].append(now)
    return True
