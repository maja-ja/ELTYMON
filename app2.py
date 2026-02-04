import streamlit as st
import pandas as pd
import json, re
from datetime import datetime, timedelta
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置
# ==========================================
st.set_page_config(page_title="Kadowsella | 陪跑教練版", page_icon="🏃", layout="wide")

# 🔥 設定：開訓日
START_DATE = datetime(2026, 2, 1)
# 🔥 設定：決戰日
EXAM_DATE = datetime(2027, 1, 20) 
LOCKDOWN_DATE = EXAM_DATE - timedelta(days=10)

SUBJECTS = ["國文", "英文", "數學A", "數學B", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

def inject_custom_css():
    st.markdown("""
        <style>
            .hero-word { font-size: 2.5rem; font-weight: 800; color: #1E293B; }
            .subject-tag { background: #3B82F6; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
            /* 偷看模式專用樣式 */
            .peek-box {
                background: #F0F9FF; border: 1px dashed #0EA5E9; padding: 10px; 
                border-radius: 8px; margin-bottom: 8px; opacity: 0.8;
            }
            .peek-blur { filter: blur(4px); user-select: none; color: #94A3B8; }
            .stButton>button { border-radius: 8px; font-weight: bold; }
            #MainMenu {visibility: hidden;} footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 進度邏輯
# ==========================================
def get_current_week():
    delta = datetime.now() - START_DATE
    if delta.days < 0: return 0 
    return (delta.days // 7) + 1

def get_record_week(date_str):
    try:
        dt = datetime.strptime(str(date_str), "%Y-%m-%d")
        delta = dt - START_DATE
        if delta.days < 0: return 0
        return (delta.days // 7) + 1
    except: return 0

def is_in_lockdown():
    return datetime.now() >= LOCKDOWN_DATE

# ==========================================
# 3. 資料庫邏輯 (含偷看權限)
# ==========================================

@st.cache_data(ttl=300)
def load_db(tick=0, admin_view=False):
    """
    admin_view=True: 會回傳所有資料 (用於教官模式 OR 偷看模式的底層數據)
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets.get("gsheets", {}).get("spreadsheet")
        if not url: return pd.DataFrame()
        
        df = conn.read(spreadsheet=url, ttl=0)
        if 'created_at' not in df.columns: df['created_at'] = "2026-02-01"
        df = df.fillna("無")
        
        # 計算週次
        df['week_num'] = df['created_at'].apply(get_record_week)
        
        # 如果不是管理員，這裡先回傳全部，由主程式決定顯示範圍
        # 這樣才能做「偷看」功能
        return df
    except Exception as e:
        st.error(f"📡 {e}")
        return pd.DataFrame()

def save_to_db(new_data):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets["gsheets"]["spreadsheet"]
        existing_df = conn.read(spreadsheet=url, ttl=0)
        new_data['created_at'] = datetime.now().strftime("%Y-%m-%d")
        new_row = pd.DataFrame([new_data])
        updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        conn.update(spreadsheet=url, data=updated_df)
        st.toast(f"✅ 已寫入 (Week {get_current_week()})", icon="💾")
    except Exception as e:
        st.error(f"寫入失敗: {e}")

# ==========================================
# 4. AI & UI
# ==========================================
def ai_decode(input_text, subject):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return None
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""請解析高中「{subject}」考點「{input_text}」。JSON: {{ "word": "{input_text}", "category": "{subject}", "roots": "核心公式/原理", "breakdown": "拆解", "definition": "定義", "native_vibe": "考試重點", "memory_hook": "口訣" }}"""
    try:
        res = model.generate_content(prompt)
        match = re.search(r'\{.*\}', res.text, re.DOTALL)
        if match: return json.loads(match.group(0))
    except: pass
    return None

def show_card(row, blur_content=False):
    """ blur_content=True 時，只顯示標題，內容模糊處理 (偷看模式) """
    if blur_content:
        st.markdown(f"""
        <div class="peek-box">
            <span class='subject-tag'>{row['category']}</span> <b>{row['word']}</b>
            <div style="margin-top:5px; font-size:0.8rem; color:#64748B;">
                🔒 內容封印中 (Week {row['week_num']})
            </div>
            <div class="peek-blur">
                這裡是很厲害的解題技巧...<br>這裡是非常重要的公式...
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"<span class='subject-tag'>{row['category']}</span> <b>{row['word']}</b>", unsafe_allow_html=True)
        st.info(f"🧬 {row['breakdown']}")
        st.caption(f"💡 {row['definition']}")
        if str(row['roots']) != "無": st.success(f"📌 {row['roots']}")

# ==========================================
# 5. 主程式
# ==========================================
def main():
    inject_custom_css()
    if 'db_tick' not in st.session_state: st.session_state.db_tick = 0
    
    # 全域資料載入 (Raw Data)
    # 注意：這裡載入全部，但後面透過邏輯嚴格控制顯示
    full_df = load_db(st.session_state.db_tick, admin_view=True)
    curr_w = get_current_week()
    
    with st.sidebar:
        st.title("🏃 陪跑教練版")
        
        # 狀態
        days_left = (EXAM_DATE - datetime.now()).days
        if is_in_lockdown():
            st.error(f"🚨 考前閉關！ (剩 {days_left} 天)")
        else:
            st.info(f"📆 當前進度：第 {curr_w} 週\n\n🎯 距離學測：{days_left} 天")
            
        if st.button("🔄 同步狀態"):
            st.session_state.db_tick += 1
            st.cache_data.clear()
            st.rerun()

        # --- [新功能] 🔮 水晶球偷看 ---
        with st.expander("🔮 偷看下週預告"):
            st.caption("忍不住想看下週教什麼？點擊下方按鈕偷瞄一眼標題！")
            if st.button("👀 偷瞄一下"):
                next_w = curr_w + 1
                if not full_df.empty:
                    next_week_data = full_df[full_df['week_num'] == next_w]
                    if not next_week_data.empty:
                        st.success(f"✨ 第 {next_w} 週 精彩預告：")
                        for _, row in next_week_data.iterrows():
                            st.markdown(f"**[{row['category']}] {row['word']}**")
                    else:
                        st.warning(f"🐢 教官還沒把第 {next_w} 週的考點放進來喔！")
                else:
                    st.warning("資料庫空的。")

        # 管理員
        is_admin = False
        with st.expander("🔑 教官登入"):
            if st.text_input("Pwd", type="password") == st.secrets.get("ADMIN_PASSWORD"):
                is_admin = True
                st.success("教官模式")

        menu = ["📅 本週訓練菜單", "🛡️ 歷史考點回顧", "🎲 隨機抽題"]
        if is_admin: menu.append("🔬 預埋考點 (未來)")
        choice = st.radio("功能", menu)

    # --- 依權限篩選資料 ---
    if is_admin:
        visible_df = full_df # 管理員看全部
    else:
        # 學生只看：週次 <= 當前週
        if not full_df.empty:
            visible_df = full_df[full_df['week_num'] <= curr_w]
        else:
            visible_df = pd.DataFrame()

    # ==========================
    # 1. 本週訓練
    # ==========================
    if choice == "📅 本週訓練菜單":
        st.title(f"📅 第 {curr_w} 週：本週任務")
        
        if is_in_lockdown():
            st.warning("🔒 閉關期不開放新進度！")
        else:
            if not visible_df.empty:
                this_week_df = visible_df[visible_df['week_num'] == curr_w]
                if this_week_df.empty:
                    st.info("🍵 本週尚無新考點。")
                else:
                    st.success(f"🔥 本週新增 {len(this_week_df)} 個考點")
                    for _, row in this_week_df.iterrows():
                        with st.expander(f"📌 {row['category']} | {row['word']}", expanded=True):
                            show_card(row)
            else:
                st.info("資料載入中...")

    # ==========================
    # 2. 歷史回顧
    # ==========================
    elif choice == "🛡️ 歷史考點回顧":
        st.title("🛡️ 知識庫存")
        if not visible_df.empty:
            history_df = visible_df[visible_df['week_num'] < curr_w]
            if history_df.empty:
                st.info("尚無歷史資料。")
            else:
                weeks = sorted(history_df['week_num'].unique(), reverse=True)
                for w in weeks:
                    w_data = history_df[history_df['week_num'] == w]
                    with st.expander(f"📂 第 {w} 週封存 ({len(w_data)} 考點)"):
                        for _, row in w_data.iterrows():
                            st.markdown("---")
                            show_card(row)

    # ==========================
    # 3. 隨機抽題
    # ==========================
    elif choice == "🎲 隨機抽題":
        st.title("🎲 隨機驗收")
        st.caption(f"📊 抽題池：共 {len(visible_df)} 題 (未來考點已過濾)")
        if st.button("🎲 抽題", type="primary", use_container_width=True): st.rerun()
        if not visible_df.empty:
            row = visible_df.sample(1).iloc[0]
            st.markdown(f"**Week {row['week_num']}**")
            show_card(row)

    # ==========================
    # 4. 預埋考點 (Admin)
    # ==========================
    elif choice == "🔬 預埋考點 (未來)" and is_admin:
        st.title("🔬 預埋考點")
        st.info(f"目前是第 {curr_w} 週。你寫入的資料會立刻存檔，但在本週訓練中會顯示。")
        
        c1, c2 = st.columns([3, 1])
        with c1: inp = st.text_input("輸入概念")
        with c2: sub = st.selectbox("科目", SUBJECTS)
        
        if st.button("生成並存入", type="primary"):
            res = ai_decode(inp, sub)
            if res:
                save_to_db(res)
                st.success("✅ 已寫入！")
                show_card(res)

if __name__ == "__main__":
    main()
