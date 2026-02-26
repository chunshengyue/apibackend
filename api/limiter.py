import os
import time
from datetime import datetime
import redis

# 💡 直接將你剛才獲取的 Upstash Redis 連線字串寫死在這裡
KV_URL = "rediss://default:AbyfAAIncDI3NDU0Y2RhNDYwNDc0NjJkOWFhMDk3NzFiNmZjNmE3YnAyNDgyODc@hopeful-mastiff-48287.upstash.io:6379"

redis_client = None
if KV_URL:
    try:
        redis_client = redis.from_url(KV_URL)
    except Exception as e:
        print(f"Redis 連線失敗: {e}")

# ================= 配置區域 =================
DAILY_DEVICE_LIMIT = 15  # 每個設備每天最多 15 次
DAILY_GLOBAL_LIMIT = 300  # 所有用戶每天加起來最多 300 次
# ==========================================

# 降級方案用的記憶體紀錄
from collections import defaultdict

_fallback_requests = defaultdict(list)


def can_request(device_id: str) -> bool:
    """ 第一步：檢查是否有調用資格（只查詢，不增加次數） """
    if not device_id:
        return True

    if redis_client:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            device_key = f"usage:device:{device_id}:{today}"
            global_key = f"usage:global:{today}"

            # 從 Redis 獲取當前次數，如果沒有紀錄則視為 0
            device_usage = int(redis_client.get(device_key) or 0)
            global_usage = int(redis_client.get(global_key) or 0)

            # 優先檢查全域額度
            if global_usage >= DAILY_GLOBAL_LIMIT:
                print(f"🚫 全域總額度已耗盡 ({global_usage}/{DAILY_GLOBAL_LIMIT})")
                return False

            # 再檢查單設備額度
            if device_usage >= DAILY_DEVICE_LIMIT:
                print(f"🚫 設備 {device_id} 今日已達上限 ({device_usage}/{DAILY_DEVICE_LIMIT})")
                return False

            return True
        except Exception as e:
            print(f"Redis 查詢失敗: {e}")
            pass

    # 降級防連擊：如果 Redis 掛了，只防 1 分鐘內的惡意請求
    now = time.time()
    valid_history = [t for t in _fallback_requests[device_id] if t > now - 60]
    if len(valid_history) >= 10:
        return False
    return True


def record_success(device_id: str):
    """ 第二步：只有在 OCR 成功後才呼叫此函數，實際扣除額度 """
    if not device_id:
        return

    if redis_client:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            device_key = f"usage:device:{device_id}:{today}"
            global_key = f"usage:global:{today}"
            total_key = "usage:global:total"  # 額外福利：紀錄歷史總成功次數！

            # 使用 Pipeline 批量執行，提高效率
            pipe = redis_client.pipeline()
            pipe.incr(device_key)
            pipe.expire(device_key, 86400)  # 24小時後過期，節約空間

            pipe.incr(global_key)
            pipe.expire(global_key, 86400)

            pipe.incr(total_key)  # 總計不用設過期時間

            pipe.execute()
        except Exception as e:
            print(f"Redis 扣除額度失敗: {e}")
    else:
        now = time.time()
        _fallback_requests[device_id].append(now)