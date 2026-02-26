from fastapi import FastAPI, Header, HTTPException, Form
from pydantic import BaseModel
import sys
import os
import re

# 將當前檔案所在的目錄加入到 Python 的搜尋路徑中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import strategy
import limiter
import config

app = FastAPI()


class OcrRequest(BaseModel):
    image: str


# ==========================================
# 解析函數
# ==========================================
def parse_baidu_table(json_data):
    if "tables_result" not in json_data or not json_data["tables_result"]: return None
    table = json_data["tables_result"][0]
    body = table.get("body", [])
    rows_map = {}
    for cell in body:
        r, c, w = cell["row_start"], cell["col_start"], cell["words"]
        w = w.replace("\n", "").strip().replace("小红书", "")
        if r not in rows_map: rows_map[r] = {}
        rows_map[r][c] = w
    output_lines = []
    for r_idx in sorted(rows_map.keys()):
        row_data = rows_map[r_idx]
        col0 = row_data.get(0, "")
        if not re.match(r'^\d+', col0): continue
        actions = [row_data.get(c, "Wait") for c in range(1, 6)]
        output_lines.append(f"{col0} {' '.join(actions)}")
    return "\n".join(output_lines)


def parse_baidu_general(json_data):
    if "words_result" not in json_data: return None
    words_list = json_data["words_result"]
    if not words_list: return ""
    if "location" in words_list[0]:
        total_height = sum([w['location']['height'] for w in words_list])
        row_threshold = (total_height / len(words_list)) * 0.6
        sorted_words = sorted(words_list, key=lambda x: x["location"]["top"])
        rows = []
        current_row = []
        current_row_top = 0
        for item in sorted_words:
            top = item["location"]["top"]
            if not current_row:
                current_row.append(item)
                current_row_top = top
            else:
                if abs(top - current_row_top) < row_threshold:
                    current_row.append(item)
                else:
                    rows.append(current_row)
                    current_row = [item]
                    current_row_top = top
        if current_row: rows.append(current_row)
        output_lines = []
        for row in rows:
            row.sort(key=lambda x: x["location"]["left"])
            texts = [x["words"].replace("\n", "").strip() for x in row]
            if re.match(r'^第?\d+', texts[0] if texts else ""):
                output_lines.append(" ".join(texts))
        return "\n".join(output_lines)

    texts = [w["words"].strip() for w in words_list]
    return " ".join(texts)


# ==========================================
# API 路由
# ==========================================
@app.get("/")
def home():
    return {"status": "running", "service": "OCR-Backend"}


@app.post("/ocr")
def ocr_endpoint(
        image: str = Form(...),
        force_mode: int = Form(None),
        x_device_id: str = Header(None, alias="X-Device-ID"),
        x_api_secret: str = Header(None, alias="X-Api-Secret")
):
    if config.API_SECRET and x_api_secret != config.API_SECRET:
        raise HTTPException(status_code=403, detail="Invalid API Secret")

    # 💡 1. 只检查是否有资格，不扣额度
    if not limiter.can_request(x_device_id):
        return {
            "error": True,
            "error_code": 429,
            "error_msg": "Too Many Requests or Quota Exceeded",
            "suggestion": "今日免费识别额度已用完，请明天再来尝试"
        }

    if not image:
        raise HTTPException(status_code=400, detail="Image is required")

    # 💡 2. 调用百度 OCR 策略
    result = strategy.execute_strategy(image, force_mode)

    # 💡 3. 如果百度报错了（没额度或QPS超了），直接原样返回，不调用记录成功的函数
    if result.get("error"):
        return result

    # 💡 4. 万事大吉！只有百度真实返回了成功数据，才去 Redis 里把次数 +1
    limiter.record_success(x_device_id)

    parsed_str = ""
    if "tables_result" in result:
        parsed_str = parse_baidu_table(result)
    elif "words_result" in result:
        parsed_str = parse_baidu_general(result)

    return {
        "status": "success",
        "_strategy_used": result.get("_strategy_used"),
        "parsed_text": parsed_str
    }