import os
import time
from datetime import datetime
import redis

KV_URL = os.getenv("KV_REST_API_URL") or os.getenv("KV_URL")

redis_client = None
if KV_URL:
    try:
        redis_client = redis.from_url(KV_URL)
    except Exception as e:
        print(f"Redis 连接失败: {e}")

# ================= 配置区域 =================
DAILY_DEVICE_LIMIT = 15  # 每个设备每天最多 15 次
DAILY_GLOBAL_LIMIT = 300  # 所有用户每天加起来最多 300 次
# ==========================================

# 降级方案用的内存记录
from collections import defaultdict

_fallback_requests = defaultdict(list)


def can_request(device_id: str) -> bool:
    """ 第一步：检查是否有调用资格（只查询，不增加次数） """
    if not device_id:
        return True

    if redis_client:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            device_key = f"usage:device:{device_id}:{today}"
            global_key = f"usage:global:{today}"

            # 从 Redis 获取当前次数，如果没有记录则视为 0
            device_usage = int(redis_client.get(device_key) or 0)
            global_usage = int(redis_client.get(global_key) or 0)

            # 优先检查全局额度
            if global_usage >= DAILY_GLOBAL_LIMIT:
                print(f"🚫 全局总额度已耗尽 ({global_usage}/{DAILY_GLOBAL_LIMIT})")
                return False

            # 再检查单设备额度
            if device_usage >= DAILY_DEVICE_LIMIT:
                print(f"🚫 设备 {device_id} 今日已达上限 ({device_usage}/{DAILY_DEVICE_LIMIT})")
                return False

            return True
        except Exception as e:
            print(f"Redis 查询失败: {e}")
            pass

    # 降级防连击：如果 Redis 挂了，只防 1 分钟内的恶意请求
    now = time.time()
    valid_history = [t for t in _fallback_requests[device_id] if t > now - 60]
    if len(valid_history) >= 10:
        return False
    return True


def record_success(device_id: str):
    """ 第二步：只有在 OCR 成功后才调用此函数，实际扣除额度 """
    if not device_id:
        return

    if redis_client:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            device_key = f"usage:device:{device_id}:{today}"
            global_key = f"usage:global:{today}"
            total_key = "usage:global:total"  # 额外福利：记录历史总成功次数！

            # 使用 Pipeline 批量执行，提高效率
            pipe = redis_client.pipeline()
            pipe.incr(device_key)
            pipe.expire(device_key, 86400)  # 24小时后过期，节约空间

            pipe.incr(global_key)
            pipe.expire(global_key, 86400)

            pipe.incr(total_key)  # 总计不用设过期时间

            pipe.execute()
        except Exception as e:
            print(f"Redis 扣除额度失败: {e}")
    else:
        now = time.time()
        _fallback_requests[device_id].append(now)