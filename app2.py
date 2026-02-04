import streamlit as st
import pandas as pd
import base64, json, re
from io import BytesIO
from gtts import gTTS
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置：學科分類優化
# ==========================================
st.set_page_config(page_title="Kadowsella | 全科衝刺版", page_icon="🎓", layout="wide")

# 定義學測與分科全科目
SUBJECTS = [
    "國文", "英文", "數學A", "數學B", "物理", 
    "化學", "生物", "地科", "歷史", "地理", "公民"
]

def inject_custom_css():
    st.markdown("""
        <style>
            .hero-word { font-size: 3rem; font-weight: 800; color: #F8FAFC; margin-bottom: 5px; }
            .subject-tag {
                background: #3B82F6; color: white; padding: 4px 12px; 
                border-radius: 6px; font-size: 0.9rem; font-weight: bold;
            }
            .breakdown-wrapper {
                background: #1E293B; padding: 25px; border-radius: 15px; 
                color: #F8FAFC; border: 1px solid #334155; line-height: 1.6;
            }
            .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心讀取與寫入 (免密碼)
# ==========================================

@st.cache_data(ttl=60)
def load_db():
    conn = st.connection("gsheets", type=GSheetsConnection)
    url = st.secrets["gsheets"]["spreadsheet"]
    df = conn.read(spreadsheet=url, ttl=0)
    return df.fillna("無")

def save_to_db(new_data):
    conn = st.connection("gsheets", type=GSheetsConnection)
    url = st.secrets["gsheets"]["spreadsheet"]
    existing_df = conn.read(spreadsheet=url, ttl=0)
    updated_df = pd.concat([existing_df, pd.DataFrame([new_data])], ignore_index=True)
    conn.update(spreadsheet=url, data=updated_df)
    st.toast(f"✅ {new_data['word']} 已存入 {new_data['category']} 資料庫", icon="💾")

# ==========================================
# 3. AI 導師：針對台灣考制優化
# ==========================================

def ai_decode(input_text, subject):
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    你現在是台灣高中升學考試（學測與分科測驗）的補教名師。
    請針對「{subject}」科目的概念「{input_text}」進行深度解析並輸出 JSON。
    
    要求：
    1. roots: 若是理科，請給出核心公式(LaTeX)或原理；若是文科，給出字源或核心思想。
    2. definition: 必須符合台灣課綱（108課綱）的專業定義。
    3. memory_hook: 提供一個好記的口訣或圖像化聯想。
    4. native_vibe: 說明這個概念在考試中的出題陷阱或重要性。
    
    JSON 格式：word, category, roots, meaning, breakdown, definition, phonetic, example, translation, native_vibe, memory_hook。
    """
    
    response = model.generate_content(prompt)
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        data['category'] = subject # 強制校正科目
        return data
    return None

# ==========================================
# 4. 介面呈現
# ==========================================

def show_card(row):
    st.markdown(f"<span class='subject-tag'>{row['category']}</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-word'>{row['word']}</div>", unsafe_allow_html=True)
    
    st.markdown(f"<div class='breakdown-wrapper'><b>🧬 知識拆解</b><br>{row['breakdown']}</div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"**🎯 核心定義**\n\n{row['definition']}")
    with c2:
        st.success(f"**💡 底層邏輯 / 公式**\n\n{row['roots']}")
        st.warning(f"**🪝 記憶口訣**\n\n{row['memory_hook']}")
    
    if row['native_vibe'] != "無":
        st.write(f"⚠️ **考試重點：** {row['native_vibe']}")

def main():
    inject_custom_css()
    st.sidebar.title("🎓 108課綱全科版")
    st.sidebar.caption("目標：國立台灣大學")
    
    page = st.sidebar.radio("功能", ["📖 考點檢索", "🔬 AI 知識填裝", "🎲 隨機抽題"])
    df = load_db()
    
    if page == "📖 考點檢索":
        st.title("🔍 全科考點搜尋")
        q = st.text_input("搜尋關鍵字（例如：光電效應、木蘭詩、邊際效用）")
        if q:
            results = df[df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
            for _, row in results.iterrows():
                with st.expander(f"{row['category']} | {row['word']}"):
                    show_card(row)
        else:
            st.dataframe(df[['category', 'word', 'definition']], use_container_width=True)
            
    elif page == "🔬 AI 知識填裝":
        st.title("🔬 AI 考點自動生成")
        col1, col2 = st.columns([3, 1])
        with col1:
            input_text = st.text_input("輸入學科概念")
        with col2:
            subject = st.selectbox("選擇科目", SUBJECTS)
            
        if st.button("生成並存入 MyDB", type="primary"):
            with st.spinner(f"正在分析 {subject} 考點..."):
                res = ai_decode(input_text, subject)
                if res:
                    show_card(res)
                    save_to_db(res)
    
    elif page == "🎲 隨機抽題":
        st.title("🎲 隨機複習")
        if st.button("下一個考點"): st.rerun()
        if not df.empty:
            show_card(df.sample(1).iloc[0])

if __name__ == "__main__":
    main()
