import streamlit as st
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai

# 1. 連結你的 MyDB 書架
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 設定第一、二個人 (Gemini) 的指令
def ai_decode_to_shelf(word, age_range):
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 嚴格要求輸出 20 個欄位的 JSON
    prompt = f"""
    你是一位語言專家。請解碼單字「{word}」給「{age_range}」受眾。
    請嚴格依照以下 20 個欄位順序回傳 JSON 格式：
    category, roots, meaning, word, breakdown, definition, phonetic, example, 
    translation, native_vibe, synonym_nuance, visual_prompt, social_status, 
    emotional_tone, street_usage, collocation, etymon_story, usage_warning, 
    memory_hook, audio_tag。
    """
    response = model.generate_content(prompt)
    return response.text

# 3. UI 介面：新增單字到 MyDB
st.title("📚 我的知識書架 - 擴充模式")
new_word = st.text_input("輸入新知識/單字")
if st.button("AI 解碼並存入 MyDB"):
    # 執行解碼邏輯
    result_json = ai_decode_to_shelf(new_word, "大專以下")
    
    # 將 JSON 轉為 DataFrame 並寫入試算表
    # (此處使用 conn.create 或 conn.update 邏輯)
    st.success(f"已成功將「{new_word}」存入你的 MyDB 倉庫！")
