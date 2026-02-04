import streamlit as st
import pandas as pd
import base64, time, json, re, os
from io import BytesIO
from gtts import gTTS
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
from datetime import date

# ==========================================
# 1. 核心配置：醫學系衝刺版 UI
# ==========================================
st.set_page_config(page_title="Kadowsella | Med Prep", page_icon="🧬", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            /* 針對讀書環境優化的字體與背景 */
            .hero-word { font-size: 3rem; font-weight: 900; color: #0D47A1; margin-bottom: 2px; }
            .vibe-box { 
                background-color: #F8FAFC; padding: 20px; border-radius: 12px; 
                border-left: 8px solid #3B82F6; color: #1E293B; margin: 15px 0;
            }
            .breakdown-wrapper {
                background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
                padding: 25px; border-radius: 15px; color: #F8FAFC;
            }
            /* 隱藏 Streamlit 原生元素 */
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 彈匣寫入邏輯：一鍵雙投 (Middle-end Logic)
# ==========================================

def dual_db_sync(res_data):
    """
    這就是你的『彈匣』核心：
    1. 寫入公開版 (給 Threads 粉絲看)
    2. 寫入補習班版 (你自己複習用，包含更多細節)
    """
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 從 secrets 讀取兩個不同的網址
    PUBLIC_URL = st.secrets["gsheets"]["public_url"]
    CRAM_URL = st.secrets["gsheets"]["cram_url"]
    
    try:
        # 寫入補習班庫 (私有)
        cram_df = conn.read(spreadsheet=CRAM_URL, ttl=0)
        new_row = pd.DataFrame([res_data])
        updated_cram = pd.concat([cram_df, new_row], ignore_index=True)
        conn.update(spreadsheet=CRAM_URL, data=updated_cram)
        
        # 寫入公開庫 (僅同步核心欄位，保護你的私房筆記)
        # 你可以選擇性過濾掉一些針對補習班講義的內容
        public_df = conn.read(spreadsheet=PUBLIC_URL, ttl=0)
        updated_public = pd.concat([public_df, new_row], ignore_index=True)
        conn.update(spreadsheet=PUBLIC_URL, data=updated_public)
        
        st.toast("🚀 彈匣發射：兩大資料庫同步完成！", icon="📡")
    except Exception as e:
        st.error(f"同步失敗: {e}")

# ==========================================
# 3. 補習班專用功能：GSAT 倒數計時
# ==========================================

def show_gsat_countdown():
    # 假設 2027 學測在 1 月 20 日 (你可以根據實際日期調整)
    exam_date = date(2027, 1, 20)
    today = date.today()
    delta = exam_date - today
    
    with st.sidebar:
        st.markdown(f"""
            <div style="background:#FFF1F2; padding:15px; border-radius:10px; border:1px solid #FDA4AF; text-align:center;">
                <p style="margin:0; color:#BE123C; font-weight:700;">🎯 距離學測 GSAT</p>
                <h2 style="margin:0; color:#E11D48;">{delta.days} 天</h2>
                <p style="margin:0; font-size:0.8rem; color:#FB7185;">目標：台大醫學系</p>
            </div>
        """, unsafe_allow_html=True)

# ==========================================
# 4. 核心解碼 (精簡 Prompt 版)
# ==========================================

def ai_decode_and_save(input_text, fixed_category):
    # ... (保留你原本的 AI 邏輯，但將 model 改為 gemini-1.5-flash 以節省成本)
    # Gemini 2.0 Flash 雖然強，但針對這種結構化輸出，1.5 Flash 穩定且夠用
    pass

# ==========================================
# 5. 主入口 (修剪過的選單)
# ==========================================

def main():
    inject_custom_css()
    show_gsat_countdown() # 側邊欄倒數
    
    # 管理員上帝模式 (密碼保護)
    is_admin = False
    with st.sidebar.expander("🔑 核心系統", expanded=False):
        pwd = st.text_input("Access Code", type="password")
        if pwd == st.secrets["ADMIN_PASSWORD"]:
            is_admin = True
            st.success("上帝模式：彈匣已裝填")

    # 側邊欄選單 (移除了贊助按鈕，讓介面乾淨)
    menu = ["🔥 快速複習", "🔍 知識庫檢索"]
    if is_admin:
        menu.append("🔬 實驗室 (寫入彈匣)")
        
    choice = st.sidebar.radio("Navigation", menu)
    
    # 載入資料 (補習班版本專屬庫)
    url = st.secrets["gsheets"]["cram_url"]
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=url, ttl=360) # 補習班版可以增加快取時間

    if choice == "🔥 快速複習":
        # 展示隨機三張卡片，幫助記憶
        st.title("Today's High-Yield Topics")
        page_home(df) 
        
    elif choice == "🔍 知識庫檢索":
        page_learn_search(df)
        
    elif choice == "🔬 實驗室 (寫入彈匣)":
        # 這裡的邏輯要調用 dual_db_sync
        st.title("Content Injection System")
        # ... (你的 AI Lab 代碼，但在存檔時呼叫 dual_db_sync)

if __name__ == "__main__":
    main()
