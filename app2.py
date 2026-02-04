import streamlit as st
import pandas as pd
import json, re
from datetime import datetime
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置
# ==========================================
st.set_page_config(page_title="Kadowsella | 學習歷程回顧", page_icon="📆", layout="wide")

SUBJECTS = ["國文", "英文", "數學A", "數學B", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

def inject_custom_css():
    st.markdown("""
        <style>
            .hero-word { font-size: 2.5rem; font-weight: 800; color: #1E293B; }
            .subject-tag { background: #3B82F6; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
            .date-header { font-size: 1.2rem; font-weight: bold; color: #475569; margin-top: 10px; }
            .breakdown-wrapper { background: #F8FAFC; padding: 15px; border-radius: 10px; border-left: 4px solid #3B82F6; }
            #MainMenu {visibility: hidden;} footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 資料庫邏輯 (新增日期處理)
# ==========================================

@st.cache_data(ttl=300)
def load_db(tick=0):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets.get("gsheets", {}).get("spreadsheet")
        if not url: return pd.DataFrame()
        
        df = conn.read(spreadsheet=url, ttl=0)
        
        # --- [關鍵修改] 確保有日期欄位 ---
        if 'created_at' not in df.columns:
            df['created_at'] = "2024-01-01" # 舊資料預設日期
            
        # 填充空值，避免分組報錯
        return df.fillna("無")
    except Exception as e:
        st.error(f"📡 資料庫讀取失敗: {e}")
        return pd.DataFrame()

def save_to_db(new_data):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets["gsheets"]["spreadsheet"]
        existing_df = conn.read(spreadsheet=url, ttl=0)
        
        # --- [關鍵修改] 自動蓋上今天的日期 ---
        new_data['created_at'] = datetime.now().strftime("%Y-%m-%d")
        
        new_row = pd.DataFrame([new_data])
        updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        
        conn.update(spreadsheet=url, data=updated_df)
        st.toast(f"✅ 已存入，日期標記：{new_data['created_at']}", icon="📅")
    except Exception as e:
        st.error(f"寫入失敗: {e}")

# ==========================================
# 3. AI 解碼 (維持原樣)
# ==========================================
def ai_decode(input_text, subject):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return None
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    請針對台灣高中「{subject}」考點「{input_text}」解析。
    輸出純 JSON：{{ "word": "{input_text}", "category": "{subject}", "roots": "核心/公式", "meaning": "意義", "breakdown": "拆解", "definition": "課綱定義", "phonetic": "音標/年代", "native_vibe": "考點陷阱", "memory_hook": "口訣" }}
    """
    try:
        response = model.generate_content(prompt)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match: return json.loads(match.group(0))
    except: pass
    return None

# ==========================================
# 4. 輔助函式：日期轉星期
# ==========================================
def get_weekday_str(date_str):
    """將 2026-02-04 轉為 (週三)"""
    try:
        dt = datetime.strptime(str(date_str), "%Y-%m-%d")
        weekdays = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
        return weekdays[dt.weekday()]
    except:
        return ""

def show_card(row, simple=False):
    """ simple=True 時顯示精簡版，適合日誌列表 """
    st.markdown(f"<span class='subject-tag'>{row['category']}</span> <b>{row['word']}</b>", unsafe_allow_html=True)
    if not simple:
        st.caption(f"💡 {row['definition']}")
        st.info(f"🧬 {row['breakdown']}")
        if str(row['roots']) != "無": st.success(f"📌 {row['roots']}")

# ==========================================
# 5. 主程式
# ==========================================
def main():
    inject_custom_css()
    if 'db_tick' not in st.session_state: st.session_state.db_tick = 0
    
    with st.sidebar:
        st.title("📆 學習日誌版")
        if st.button("🔄 同步資料庫"):
            st.session_state.db_tick += 1
            st.cache_data.clear()
            st.rerun()
        
        # 管理員登入
        is_admin = False
        with st.expander("🔑 管理員"):
            if st.text_input("Pwd", type="password") == st.secrets.get("ADMIN_PASSWORD"):
                is_admin = True
        
        menu = ["📅 學習日誌 (按日期)", "📖 考點檢索", "🎲 隨機複習"]
        if is_admin: menu.append("🔬 AI 彈匣填裝")
        choice = st.radio("功能", menu)

    df = load_db(st.session_state.db_tick)

    # --- 功能：學習日誌 (按日期分組) ---
    if choice == "📅 學習日誌 (按日期)":
        st.title("📅 學習歷程回顧")
        
        if df.empty:
            st.warning("目前沒有資料。")
        else:
            # 1. 確保日期欄位格式正確
            df['created_at'] = df['created_at'].astype(str).replace('nan', '歷史存檔')
            
            # 2. 取得所有不重複日期，並降序排列 (最新的日期在上面)
            unique_dates = sorted(df['created_at'].unique(), reverse=True)
            
            # 3. 迴圈生成每一天的區塊
            for d in unique_dates:
                # 篩選該日期的資料
                day_data = df[df['created_at'] == d]
                count = len(day_data)
                weekday = get_weekday_str(d)
                
                # 標題顯示：2026-02-04 (週三) - 共 5 個考點
                label = f"{d} {weekday} · 複習了 {count} 個考點"
                
                with st.expander(label, expanded=(d == unique_dates[0])): # 預設只展開最新的一天
                    for _, row in day_data.iterrows():
                        st.markdown("---")
                        show_card(row, simple=False)

    # --- 功能：AI 彈匣填裝 (自動加日期) ---
    elif choice == "🔬 AI 彈匣填裝" and is_admin:
        st.title("🔬 AI 考點自動生成")
        c1, c2 = st.columns([3, 1])
        with c1: inp = st.text_input("輸入概念")
        with c2: sub = st.selectbox("科目", SUBJECTS)
        
        if st.button("生成並存入", type="primary"):
            with st.spinner("AI 運算中..."):
                res = ai_decode(inp, sub)
                if res:
                    save_to_db(res) # 這裡會自動加上今天的日期
                    st.success("✅ 已存入日誌！")
                    show_card(res)

    # --- 其他功能保持不變 ---
    elif choice == "📖 考點檢索":
        st.title("🔍 考點檢索")
        q = st.text_input("搜尋...")
        if q:
            res = df[df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
            for _, r in res.iterrows(): show_card(r)
            
    elif choice == "🎲 隨機複習":
        st.title("🎲 隨機抽題")
        if st.button("Next"): st.rerun()
        if not df.empty: show_card(df.sample(1).iloc[0])

if __name__ == "__main__":
    main()
