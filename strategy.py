import config
import baidu_client

# 定义策略链
# 格式: (模式, 账号索引)
# 账号索引 0 = 账号A, 1 = 账号B
STRATEGY_CHAIN = [
    ("table", 0),  # 优先：表格 + 账号A
    ("table", 1),  # 其次：表格 + 账号B
    ("accurate", 0),  # 再次：含位置 + 账号A
    ("accurate", 1),  # ...
    ("basic", 0),  # 保底：普通 + 账号A
    ("basic", 1)
]


def execute_strategy(image_base64):
    accounts = config.get_accounts()
    if not accounts:
        return {"error": "No accounts configured"}

    last_error = None

    for mode, acc_idx in STRATEGY_CHAIN:
        # 账号索引越界保护 (万一你只配了1个账号)
        if acc_idx >= len(accounts):
            continue

        account = accounts[acc_idx]
        print(f"Trying Strategy: {mode} with Account {acc_idx}...")

        result = baidu_client.call_ocr(mode, account, image_base64)

        # 检查是否成功
        # 百度成功时通常没有 error_code，或者 error_code = 0
        if "error_code" not in result or result["error_code"] == 0:
            # 成功！直接返回 (暂时透传)
            # 可以在这里加个标记，告诉前端用了哪个模式
            result["_strategy_used"] = f"{mode}_acc{acc_idx}"
            return result

        # 记录错误
        error_code = result.get("error_code")
        error_msg = result.get("error_msg", "Unknown")
        print(f"  -> Failed: {error_code} - {error_msg}")

        # 关键：判断是否需要切换策略
        # 17: Open api daily request limit reached (日额度超限)
        # 18: Open api qps request limit reached (QPS超限)
        # 19: Open api total request limit reached
        if error_code in [17, 18, 19]:
            # 限流了，继续下一个策略
            last_error = result
            continue

        # 其他错误 (比如图片太模糊、格式不对)，通常换账号也没用，但换模式可能有用
        # 这里选择继续尝试下一个降级策略
        last_error = result

    # 所有策略都失败
    return {
        "error": "All strategies failed",
        "last_baidu_error": last_error
    }
