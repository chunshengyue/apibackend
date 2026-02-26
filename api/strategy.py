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


def execute_strategy(image_base64, force_mode=None):
    # 💡 新增參數 force_mode=None

    accounts = config.get_accounts()
    if not accounts:
        return {"error": "No accounts configured"}

    # 💡 根據 force_mode 動態決定要跑的策略鏈
    if force_mode == 0:
        current_chain = [("table", 0), ("table", 1)]
    elif force_mode == 1:
        current_chain = [("accurate", 0), ("accurate", 1)]
    elif force_mode == 2:
        current_chain = [("basic", 0), ("basic", 1)]
    else:
        # 如果沒傳，或者傳了不認識的數字，就跑預設的完整降級策略
        current_chain = STRATEGY_CHAIN

    last_error = None

    # 💡 這裡改成遍歷 current_chain
    for mode, acc_idx in current_chain:
        # 账号索引越界保护 (万一你只配了1个账号)
        if acc_idx >= len(accounts):
            continue

        account = accounts[acc_idx]
        print(f"Trying Strategy: {mode} with Account {acc_idx}...")

        result = baidu_client.call_ocr(mode, account, image_base64)

        # 检查是否成功
        if "error_code" not in result or result["error_code"] == 0:
            # 成功！直接返回 (暂时透传)
            result["_strategy_used"] = f"{mode}_acc{acc_idx}"
            return result

        # 记录错误
        error_code = result.get("error_code")
        error_msg = result.get("error_msg", "Unknown")
        print(f"  -> Failed: {error_code} - {error_msg}")

        # 判断是否需要切换策略
        if error_code in [17, 18, 19]:
            # 限流了，继续下一个策略
            last_error = result
            continue

        last_error = result

    # 所有策略都失败
    return {
        "error": "All strategies failed",
        "last_baidu_error": last_error
    }

