import streamlit as st
import pandas as pd
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import time

# ==========================================
# 0. 基礎配置與安全性
# ==========================================
st.set_page_config(page_title="Etymon Admin", page_icon="⚙️", layout="centered")

def check_password():
    """簡單的密碼檢查"""
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
    
    if not st.session_state.admin_authenticated:
        st.title("🔐 管理員登入")
        pwd = st.text_input("輸入管理密碼", type="password")
        if st.button("進入戰情室"):
            if pwd == st.secrets.get("ADMIN_PASSWORD", "0000"):
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("密碼錯誤")
        return False
    return True

# ==========================================
# 1. 核心工具與 AI 邏輯
# ==========================================

def get_spreadsheet_url():
    return st.secrets["connections"]["gsheets"]["spreadsheet"]

@st.cache_data(ttl=60)
def load_full_db():
    conn = st.connection("gsheets", type=GSheetsConnection)
    return conn.read(spreadsheet=get_spreadsheet_url(), ttl=0)

def ai_generate_word_data(word, category):
    """呼叫 AI 生成標準的 JSON 單字資料"""
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    請以「{category}」專家的視角，解碼單字「{word}」。
    請直接輸出 JSON 格式，不含 markdown 代碼塊，欄位如下：
    {{
        "category": "{category}",
        "roots": "字根源頭/核心邏輯",
        "meaning": "本質意義",
        "word": "{word}",
        "breakdown": "結構拆解",
        "definition": "易懂的定義",
        "phonetic": "音標/發音提示",
        "example": "生活化例句",
        "translation": "中文翻譯",
        "native_vibe": "專家心得"
    }}
    """
    try:
        response = model.generate_content(prompt)
        # 清理 JSON 字串
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"AI 生成失敗: {e}")
        return None

# ==========================================
# 2. UI 介面 (爆改管理員版)
# ==========================================

def admin_ui():
    st.markdown("""
        <style>
            .main { background-color: #f0f2f6; }
            .stButton > button { width: 100%; border-radius: 10px; }
            .data-card { background: white; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-left: 5px solid #1976D2; }
        </style>
    """, unsafe_allow_html=True)

    st.title("🧪 Etymon 戰情室")
    
    tab1, tab2, tab3 = st.tabs(["🆕 新增單字", "🔍 管理庫存", "📊 數據統計"])

    # --- Tab 1: AI 輔助新增 ---
    with tab1:
        st.subheader("🤖 AI 自動補完")
        new_w = st.text_input("要新增的單字", placeholder="例如: Entropy")
        new_c = st.selectbox("所屬領域", ["英語辭源", "物理科學", "商業商戰", "人工智慧", "心理學", "自定義"])
        
        if st.button("✨ 呼叫 AI 生成資料庫內容"):
            with st.spinner("AI 正在解析中..."):
                res = ai_generate_word_data(new_w, new_c)
                if res:
                    st.session_state.temp_data = res
                    st.success("解析成功！請檢查下方內容並確認存檔。")

        if "temp_data" in st.session_state:
            with st.form("confirm_form"):
                d = st.session_state.temp_data
                f_word = st.text_input("單字", d['word'])
                f_roots = st.text_input("字根", d['roots'])
                f_def = st.text_area("定義", d['definition'])
                f_ex = st.text_area("例句", d['example'])
                f_cat = st.text_input("分類", d['category'])
                
                if st.form_submit_button("💾 確認存入雲端資料庫"):
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    df = load_full_db()
                    new_row = pd.DataFrame([d])
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    conn.update(spreadsheet=get_spreadsheet_url(), data=updated_df)
                    st.balloons()
                    st.success(f"已存入：{f_word}")
                    del st.session_state.temp_data

    # --- Tab 2: 庫存管理 (搜尋、修改、刪除) ---
    with tab2:
        df = load_full_db()
        st.subheader(f"目前總量: {len(df)}")
        search = st.text_input("🔍 搜尋現有單字進行管理")
        
        if search:
            match = df[df['word'].str.contains(search, case=False)]
            for idx, row in match.iterrows():
                with st.expander(f"📦 {row['word']} ({row['category']})"):
                    st.write(row.to_dict())
                    if st.button("🗑️ 刪除此筆資料", key=f"del_{idx}"):
                        df = df.drop(idx)
                        conn = st.connection("gsheets", type=GSheetsConnection)
                        conn.update(spreadsheet=get_spreadsheet_url(), data=df)
                        st.warning("已刪除，請重新整理頁面。")
                        st.rerun()

    # --- Tab 3: 數據統計 (Metrics) ---
    with tab3:
        st.subheader("📈 用戶意圖統計")
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            m_df = conn.read(spreadsheet=get_spreadsheet_url(), worksheet="metrics", ttl=0)
            st.dataframe(m_df.sort_values(by='count', ascending=False), use_container_width=True)
            
            if st.button("🧹 重設統計數據"):
                empty_m = pd.DataFrame(columns=['label', 'count'])
                conn.update(spreadsheet=get_spreadsheet_url(), worksheet="metrics", data=empty_m)
                st.rerun()
        except:
            st.info("尚無統計數據。")

# ==========================================
# 3. 執行入口
# ==========================================
if __name__ == "__main__":
    if check_password():
        admin_ui()
