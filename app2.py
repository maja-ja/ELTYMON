import streamlit as st
import pandas as pd
import json, re
from datetime import datetime, timedelta
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置 & 無限循環大腦
# ==========================================
st.set_page_config(page_title="Kadowsella | 無限賽季版", page_icon="♾️", layout="wide")

SUBJECTS = ["國文", "英文", "數學A", "數學B", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

def get_cycle_info():
    """
    自動計算當前的「年度賽季」資訊。
    開訓日：每年 3 月 1 日 (Week 1)
    學測日：每年 1 月 15 日
    """
    now = datetime.now()
    current_year = now.year
    
    # 判斷賽季起始日：1-2月算去年的循環，3月後算今年的
    if now.month < 3:
        cycle_start = datetime(current_year - 1, 3, 1)
    else:
        cycle_start = datetime(current_year, 3, 1)

    # 判斷學測目標日：如果今年的 1/15 過了，目標就是明年的 1/15
    exam_date = datetime(current_year, 1, 15)
    if now > exam_date:
        exam_date = datetime(current_year + 1, 1, 15)
        
    lockdown_date = exam_date - timedelta(days=10)
    days_left = (exam_date - now).days
    
    # 計算週次
    delta_from_start = now - cycle_start
    current_week = (delta_from_start.days // 7) + 1
    if current_week < 1: current_week = 1
    
    return {
        "start_date": cycle_start,
        "exam_date": exam_date,
        "lockdown_date": lockdown_date,
        "week_num": current_week,
        "days_left": days_left,
        "season_label": f"{cycle_start.year}-{exam_date.year} 賽季"
    }

CYCLE = get_cycle_info()

def inject_custom_css():
    st.markdown("""
        <style>
            .hero-word { font-size: 2.8rem; font-weight: 800; color: #1E293B; }
            .subject-tag { background: #3B82F6; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
            .cycle-badge { 
                background: #0F172A; color: #38BDF8; padding: 5px; 
                border-radius: 10px; text-align: center; border: 1px solid #38BDF8; font-weight: bold;
            }
            .breakdown-wrapper { background: #F8FAFC; padding: 20px; border-radius: 12px; border-left: 5px solid #3B82F6; }
            #MainMenu {visibility: hidden;} footer {visibility: hidden;}
            .peek-blur { filter: blur(4px); opacity: 0.5; user-select: none; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 資料庫邏輯
# ==========================================

@st.cache_data(ttl=300)
def load_db(tick=0):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets.get("gsheets", {}).get("spreadsheet")
        df = conn.read(spreadsheet=url, ttl=0)
        if 'created_at' not in df.columns: df['created_at'] = "2025-03-01"
        return df.fillna("無")
    except Exception as e:
        st.error(f"📡 資料庫讀取失敗: {e}")
        return pd.DataFrame()

def save_to_db(new_data):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets["gsheets"]["spreadsheet"]
        existing_df = conn.read(spreadsheet=url, ttl=0)
        new_data['created_at'] = datetime.now().strftime("%Y-%m-%d")
        updated_df = pd.concat([existing_df, pd.DataFrame([new_data])], ignore_index=True)
        conn.update(spreadsheet=url, data=updated_df)
        st.toast(f"✅ 存入 Week {CYCLE['week_num']}", icon="💾")
    except Exception as e:
        st.error(f"寫入失敗: {e}")

# ==========================================
# 3. 顯示與輔助功能
# ==========================================

def get_record_week(date_str):
    try:
        dt = datetime.strptime(str(date_str), "%Y-%m-%d")
        delta = dt - CYCLE["start_date"]
        return (delta.days // 7) + 1
    except: return 0

def show_card(row):
    st.markdown(f"<span class='subject-tag'>{row['category']}</span> <b>{row['word']}</b>", unsafe_allow_html=True)
    st.markdown(f"<div class='breakdown-wrapper'>🧬 {row['breakdown']}</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.info(f"💡 {row['definition']}")
    with c2: st.success(f"📌 {row['roots']}")

# ==========================================
# 4. 主程式頁面
# ==========================================

def main():
    inject_custom_css()
    if 'db_tick' not in st.session_state: st.session_state.db_tick = 0
    full_df = load_db(st.session_state.db_tick)
    
    is_admin = False
    with st.sidebar:
        st.title("♾️ 永恆戰情室")
        st.markdown(f"<div class='cycle-badge'>{CYCLE['season_label']}</div>", unsafe_allow_html=True)
        
        # 狀態顯示邏輯
        days_left = CYCLE["days_left"]
        if days_left > 330:
            st.success("🍃 賽季交替期：2026 戰役結束")
            st.write(f"距離 2027 學測剩 {days_left} 天")
        elif datetime.now() >= CYCLE["lockdown_date"]:
            st.error(f"🚨 考前 10 天閉關！ (剩 {days_left} 天)")
        else:
            st.info(f"📆 本季進度：第 {CYCLE['week_num']} 週\n\n🎯 距離學測：{days_left} 天")

        if st.button("🔄 同步雲端"):
            st.session_state.db_tick += 1
            st.cache_data.clear()
            st.rerun()

        # 🔮 偷看功能
        with st.expander("🔮 偷看下週預告"):
            if st.button("👀 偷瞄"):
                next_w = CYCLE["week_num"] + 1
                if not full_df.empty:
                    full_df['dynamic_week'] = full_df['created_at'].apply(get_record_week)
                    p_df = full_df[full_df['dynamic_week'] == next_w]
                    if not p_df.empty:
                        for _, r in p_df.iterrows(): st.write(f"· [{r['category']}] {r['word']}")
                    else: st.write("尚無預告。")

        with st.expander("🔑 管理員"):
            if st.text_input("Pwd", type="password") == st.secrets.get("ADMIN_PASSWORD"):
                is_admin = True
        
        menu = ["📅 本週訓練菜單", "🛡️ 歷史考點回顧", "🎲 隨機抽題"]
        if is_admin: menu.append("🔬 預埋考點")
        choice = st.radio("功能", menu)

    # 資料分流
    if not full_df.empty:
        full_df['dynamic_week'] = full_df['created_at'].apply(get_record_week)
        # 學生只能看到當前賽季且已解鎖的
        if is_admin: visible_df = full_df
        else: visible_df = full_df[(full_df['dynamic_week'] > 0) & (full_df['dynamic_week'] <= CYCLE["week_num"])]
    else: visible_df = pd.DataFrame()

    if choice == "📅 本週訓練菜單":
        st.title(f"📅 第 {CYCLE['week_num']} 週任務")
        if not visible_df.empty:
            this_week = visible_df[visible_df['dynamic_week'] == CYCLE['week_num']]
            if this_week.empty: st.info("本週尚無新考點。")
            else:
                for _, r in this_week.iterrows():
                    with st.expander(f"📌 {r['word']}", expanded=True): show_card(r)
        else: st.info("等待開訓...")

    elif choice == "🛡️ 歷史考點回顧":
        st.title("🛡️ 知識庫存")
        if not visible_df.empty:
            hist = visible_df[visible_df['dynamic_week'] < CYCLE['week_num']]
            weeks = sorted(hist['dynamic_week'].unique(), reverse=True)
            for w in weeks:
                with st.expander(f"📂 第 {w} 週回顧"):
                    for _, r in hist[hist['dynamic_week'] == w].iterrows():
                        st.markdown("---")
                        show_card(r)

    elif choice == "🎲 隨機抽題":
        st.title("🎲 隨機驗收")
        if st.button("🎲 抽題"): st.rerun()
        if not visible_df.empty:
            row = visible_df.sample(1).iloc[0]
            st.caption(f"來自 Week {row['dynamic_week']}")
            show_card(row)

    elif choice == "🔬 預埋考點" and is_admin:
        st.title("🔬 AI 生成")
        inp = st.text_input("輸入概念")
        sub = st.selectbox("科目", SUBJECTS)
        if st.button("生成並存入"):
            # 此處呼叫之前定義過的 ai_decode 函式
            st.write("AI 運作中... (請確保程式碼包含 ai_decode)")

if __name__ == "__main__":
    main()
