import json
import os
import re

# 檔案路徑設定
STUDIO_OUTPUT_FILE = "studio_output.json"
MASTER_DB_FILE = "master_db.json"

def clean_json_string(raw_str):
    """處理無效逸出字元與 AI 斷頭問題"""
    # 1. 移除 Markdown 標籤 (```json ... ```)
    clean_str = re.sub(r'```json\s*|```', '', raw_str).strip()
    
    # 2. 修復無效的反斜線 (關鍵！)
    # 將單個反斜線替換為雙斜線，除非它已經是合法的逸出字元
    # 這裡用一個簡單的替換來處理大多數 LaTeX 和路徑問題
    clean_str = clean_str.replace('\\', '\\\\')
    # 還原已經被雙重轉義的換行符號
    clean_str = clean_str.replace('\\\\n', '\\n').replace('\\\\"', '\\"')

    # 3. 自動補齊斷頭的括號
    if not clean_str.endswith(']'):
        last_brace = clean_str.rfind('}')
        if last_brace != -1:
            clean_str = clean_str[:last_brace+1] + ']'
            print("⚠️ 偵測到 JSON 截斷，已自動補齊結尾括號")
            
    return clean_str

def merge_data():
    # 1. 讀取/初始化主資料庫
    master_db = {}
    if os.path.exists(MASTER_DB_FILE):
        with open(MASTER_DB_FILE, "r", encoding="utf-8") as f:
            try:
                master_db = json.load(f)
            except json.JSONDecodeError:
                print("⚠️ 主資料庫損壞，備份後重新建立")
                
    # 2. 讀取並清洗 Studio 輸出
    if not os.path.exists(STUDIO_OUTPUT_FILE):
        print(f"❌ 找不到 {STUDIO_OUTPUT_FILE}")
        return

    with open(STUDIO_OUTPUT_FILE, "r", encoding="utf-8") as f:
        raw_content = f.read()
        if not raw_content.strip():
            print("❌ studio_output.json 是空的")
            return
            
        try:
            # 嘗試直接讀取，若失敗則啟動清洗
            try:
                new_data_list = json.loads(raw_content)
            except json.JSONDecodeError:
                cleaned_content = clean_json_string(raw_content)
                new_data_list = json.loads(cleaned_content)
        except json.JSONDecodeError as e:
            print(f"❌ 無法修復 JSON 格式：{e}")
            print("💡 建議：檢查單字定義中是否有『未轉義的雙引號』，那是 AI 最常出錯的地方")
            return

    # 3. 轉換與合併 (Array to Dict)
    success_count = 0
    for item in new_data_list:
        word_key = item.get("word")
        if not word_key: continue
        
        clean_key = str(word_key).strip().lower()
        master_db[clean_key] = item
        success_count += 1

    # 4. 寫回主資料庫
    with open(MASTER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(master_db, f, ensure_ascii=False, indent=2)

    print(f"✅ 成功處理！新增/更新：{success_count} 筆")
    print(f"📚 目前總單字量：{len(master_db)}")

if __name__ == "__main__":
    merge_data()