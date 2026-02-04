import streamlit as st
import pandas as pd
import json, re
from datetime import datetime
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置與 CSS
# ==========================================
st.set_page_config(page_title="Kadowsella | 116學測戰情室", page_icon="🎓", layout="wide")

SUBJECTS = ["國文", "英文", "數學A", "數學B", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

def inject_custom_css():
    st.markdown("""
        <style>
            .hero-word { font-size: 3rem; font-weight: 800; color: #1E293B; margin-bottom: 5px; }
            .subject-tag { background: #3B82F6; color: white; padding: 4px 12px; border-radius: 6px; font-size: 0.9rem; font-weight: bold; }
            .breakdown-wrapper { background: #F1F5F9; padding: 25px; border-radius: 15px; color: #1E293B; border-left: 5px solid #3B82F6; line-height: 1.8; }
            .stButton>button { border-radius: 8px; font-weight: bold; }
            /* 隱藏預設元素 */
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 資料庫讀取與寫入
# ==========================================

@st.cache_data(ttl=300)
def load_db(tick=0):
    """讀取資料庫 (支援強制刷新)"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # 使用 safe get 避免 KeyError
        url = st.secrets.get("gsheets", {}).get("spreadsheet")
        if not url: return pd.DataFrame()
        
        df = conn.read(spreadsheet=url, ttl=0)
        return df.fillna("無")
    except Exception as e:
        st.error(f"📡 資料庫連線失敗: {e}")
        return pd.DataFrame()

def save_to_db(new_data):
    """將 AI 生成的資料寫入 Google Sheets"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets["gsheets"]["spreadsheet"]
        existing_df = conn.read(spreadsheet=url, ttl=0)
        
        # 建立新的一列 DataFrame
        new_row = pd.DataFrame([new_data])
        updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        
        conn.update(spreadsheet=url, data=updated_df)
        st.toast(f"✅ 「{new_data['word']}」已成功存入資料庫！", icon="💾")
    except Exception as e:
        st.error(f"寫入失敗: {e}")

# ==========================================
# 3. AI 解碼核心 (Gemini)
# ==========================================

def ai_decode(input_text, subject):
    """呼叫 Gemini 進行學科解析"""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("❌ 找不到 GEMINI_API_KEY，請檢查 Secrets 設定。")
        return None

    genai.configure(api_key=api_key)
    # 使用 flash 模型速度快且便宜
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    你現在是台灣高中升學考試（學測/分科測驗）的補教名師。
    請針對「{subject}」科目的概念「{input_text}」進行深度解析。
    
    【輸出要求】：
    1. roots: 若是理科，給出核心公式(LaTeX格式)或原理；若是文科，給出字源或核心思想。
    2. definition: 符合 108 課綱的專業定義，簡潔精準。
    3. breakdown: 條列式拆解重點，使用 \\n 換行。
    4. memory_hook: 提供一個好記的口訣、諧音或圖像聯想。
    5. native_vibe: 說明此考點在考試中的常見陷阱或重要性 (e.g. "常考多選題", "易混淆觀念")。
    
    【格式要求】：
    請直接輸出純 JSON 格式，不要有 Markdown 標記，包含以下欄位：
    {{
        "word": "{input_text}",
        "category": "{subject}",
        "roots": "",
        "meaning": "",
        "breakdown": "",
        "definition": "",
        "phonetic": "",
        "example": "",
        "translation": "",
        "native_vibe": "",
        "memory_hook": ""
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        # 清洗並提取 JSON
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        st.error(f"AI 生成錯誤: {e}")
    return None

# ==========================================
# 4. 卡片顯示組件
# ==========================================

def show_card(row):
    st.markdown(f"<span class='subject-tag'>{row['category']}</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-word'>{row['word']}</div>", unsafe_allow_html=True)
    
    st.markdown(f"<div class='breakdown-wrapper'><b>🧬 考點拆解</b><br>{row['breakdown']}</div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"**🎯 核心定義**\n\n{row['definition']}")
    with c2:
        st.success(f"**💡 底層邏輯 / 公式**\n\n{row['roots']}")
        st.warning(f"**🪝 記憶口訣**\n\n{row['memory_hook']}")
        
    if str(row.get('native_vibe')) != "無":
        st.caption(f"⚠️ 考試重點：{row['native_vibe']}")

# ==========================================
# 5. 主程式入口
# ==========================================

def main():
    inject_custom_css()
    
    # 初始化刷新計數器
    if 'db_tick' not in st.session_state: st.session_state.db_tick = 0
    
    # --- 側邊欄：導航與控制 ---
    with st.sidebar:
        st.title("🎓 116學測戰情室")
        
        # 1. 倒數計時
        days_left = (datetime(2027, 1, 20) - datetime.now()).days
        st.metric("🎯 距離 GSAT 倒數", f"{days_left} 天")
        
        # 2. 強制刷新按鈕
        if st.button("🔄 同步雲端資料", use_container_width=True):
            st.session_state.db_tick += 1
            st.cache_data.clear()
            st.toast("正在同步最新考點...", icon="⏳")
            st.rerun()
            
        st.markdown("---")
        
        # 3. 管理員登入 (上帝模式)
        is_admin = False
        with st.expander("🔑 管理員登入"):
            pwd = st.text_input("Access Code", type="password")
            # 請確認 secrets.toml 裡有設定 ADMIN_PASSWORD
            if pwd == st.secrets.get("ADMIN_PASSWORD"):
                is_admin = True
                st.success("🔓 上帝模式啟動")
        
        st.markdown("---")
        
        # 選單邏輯：只有管理員看得到「AI 彈匣填裝」
        menu = ["📖 考點檢索", "🎲 隨機複習"]
        if is_admin: menu.append("🔬 AI 彈匣填裝")
        
        choice = st.radio("功能導覽", menu)

    # 讀取資料
    df = load_db(st.session_state.db_tick)

    # --- 頁面路由 ---
    
    if choice == "📖 考點檢索":
        st.title("🔍 全科考點搜尋")
        q = st.text_input("輸入關鍵字 (如: 光電效應, 邊際效用)...")
        if q:
            # 全文檢索
            results = df[df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
            if not results.empty:
                for _, row in results.iterrows():
                    with st.expander(f"📘 {row['category']} | {row['word']}"):
                        show_card(row)
            else:
                st.warning("找不到相關考點，試試其他關鍵字？")
        else:
            # 預設顯示前 50 筆簡表
            if not df.empty:
                st.dataframe(df[['category', 'word', 'definition']].head(50), use_container_width=True)
            else:
                st.info("資料庫目前是空的，請管理員進行填裝。")

    elif choice == "🎲 隨機複習":
        st.title("🎲 隨機抽題複習")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🎲 換一個考點", type="primary", use_container_width=True):
                st.rerun()
        
        if not df.empty:
            random_row = df.sample(1).iloc[0]
            show_card(random_row)
        else:
            st.warning("資料庫是空的，無法抽題。")

    elif choice == "🔬 AI 彈匣填裝" and is_admin:
        st.title("🔬 AI 考點自動生成 (管理員模式)")
        st.info("在此輸入學科概念，AI 將自動拆解並存入資料庫。")
        
        c1, c2 = st.columns([3, 1])
        with c1:
            input_text = st.text_input("輸入要拆解的概念", placeholder="例如：包立不相容原理")
        with c2:
            subject = st.selectbox("選擇科目", SUBJECTS)
        
        if st.button("🚀 生成並存入資料庫", type="primary", use_container_width=True):
            if not input_text:
                st.warning("請輸入內容！")
            else:
                with st.spinner(f"正在以【{subject}】名師視角進行拆解..."):
                    # 1. 呼叫 AI 生成
                    res_data = ai_decode(input_text, subject)
                    
                    if res_data:
                        # 2. 顯示預覽卡片
                        st.subheader("👀 預覽生成結果")
                        show_card(res_data)
                        
                        # 3. 寫入資料庫
                        save_to_db(res_data)
                        
                        # 4. 放煙火慶祝
                        st.balloons()

if __name__ == "__main__":
    main()
