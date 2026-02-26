import os

# 读取环境变量中的账号配置
# 格式: AK1,SK1|AK2,SK2
# 例如: "API_KEY_A,SECRET_KEY_A|API_KEY_B,SECRET_KEY_B"
ACCOUNTS_ENV = os.getenv("BAIDU_ACCOUNTS", "")


def get_accounts():
    accounts = []
    if not ACCOUNTS_ENV:
        return accounts

    pairs = ACCOUNTS_ENV.split("|")
    for p in pairs:
        if "," in p:
            ak, sk = p.split(",")
            accounts.append({"ak": ak.strip(), "sk": sk.strip()})
    return accounts


# 简单的 API 密钥保护（可选，防止完全公开访问）
API_SECRET = os.getenv("API_SECRET", "my-secret-123")
