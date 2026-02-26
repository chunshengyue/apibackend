from fastapi import FastAPI, Header, HTTPException, Form

from pydantic import BaseModel
import sys
import os

# 💡 新增這兩行：將當前檔案所在的目錄 (即 api/) 加入到 Python 的搜尋路徑中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import strategy

import limiter

import config



app = FastAPI()





class OcrRequest(BaseModel):

    image: str  # Base64 字符串





@app.get("/")

def home():

    return {"status": "running", "service": "OCR-Backend"}





@app.post("/ocr")

def ocr_endpoint(

        image: str = Form(...),  # 接收 Form-Data 中的 image 字段

        x_device_id: str = Header(None, alias="X-Device-ID"),  # 从 Header 读取

        x_api_secret: str = Header(None, alias="X-Api-Secret")  # 简单鉴权

):

    # 1. 简单鉴权 (防止被扫描)

    if config.API_SECRET and x_api_secret != config.API_SECRET:

        raise HTTPException(status_code=403, detail="Invalid API Secret")



    # 2. 限流检查

    if not limiter.check_limit(x_device_id):

        raise HTTPException(status_code=429, detail="Too Many Requests")



    # 3. 执行策略

    if not image:

        raise HTTPException(status_code=400, detail="Image is required")



    result = strategy.execute_strategy(image)



    return result


