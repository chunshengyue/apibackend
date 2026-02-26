import config
import baidu_client
import random


def execute_strategy(image_base64, force_mode=None):
    accounts = config.get_accounts()
    if not accounts:
        return {"error": True, "error_msg": "No accounts configured", "suggestion": "服务器未配置账号"}

    # 根据传入参数决定要跑的模式链条
    if force_mode == 0:
        modes_to_run = ["table"]
    elif force_mode == 1:
        modes_to_run = ["accurate"]
    elif force_mode == 2:
        modes_to_run = ["basic"]
    else:
        # 默认：完整的降级链条
        modes_to_run = ["table", "accurate", "basic"]

    last_error = None

    for mode in modes_to_run:
        # 💡 针对不同的模式分配账号
        if mode == "basic":
            # 需求：模式2只有第二个key能调用
            if len(accounts) > 1:
                acc_indices = [1]
            else:
                continue  # 如果没有配置第二个号，直接跳过这个模式
        else:
            # 需求：其他模式两个号轮流（随机分摊）
            acc_indices = list(range(len(accounts)))
            random.shuffle(acc_indices)  # 随机打乱，如 [1, 0] 或 [0, 1]

        for acc_idx in acc_indices:
            account = accounts[acc_idx]
            print(f"👉 尝试策略: {mode} + 账号 {acc_idx}")

            result = baidu_client.call_ocr(mode, account, image_base64)

            # ✅ 成功：没有 error_code 或 error_code 为 0
            if "error_code" not in result or result["error_code"] == 0:
                result["_strategy_used"] = f"{mode}_acc{acc_idx}"
                return result

            # ❌ 失败：记录错误
            error_code = result.get("error_code")
            error_msg = result.get("error_msg", "Unknown error")
            last_error = result
            print(f"  -> 失败: {error_code} - {error_msg}")

            # 核心判断：17(日额度超限), 18(QPS并发超限), 19(总额度超限)
            if error_code in [17, 18, 19]:
                # 触发降级机制：继续尝试链条中的下一个账号或下一个模式
                continue

                # 如果是其他严重错误 (如图片格式错误、Token失效)，直接终止并返回给前端
            return {
                "error": True,
                "error_code": error_code,
                "error_msg": error_msg,
                "suggestion": "图像格式错误或配置失效，请重试"
            }

    # 如果所有循环都跑完了，依然没有 return 成功结果，说明额度全用光了或全遇上了 QPS 限制
    final_code = last_error.get("error_code") if last_error else -1
    suggestion = "识别失败，请稍后重试"

    if final_code in [17, 19]:
        suggestion = "本月 OCR 免费额度已耗尽，请联系开发者！"
    elif final_code == 18:
        suggestion = "当前使用人数过多 (并发受限)，请再试一次！"

    return {
        "error": True,
        "error_code": final_code,
        "error_msg": last_error.get("error_msg") if last_error else "Unknown",
        "suggestion": suggestion
    }