import streamlit as st
import pandas as pd
import json, re, io, time, urllib.parse, hashlib
from datetime import datetime, timedelta
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
from gtts import gTTS

# ==========================================
# 1. 核心配置 & 116 戰情邏輯
# ==========================================
st.set_page_config(page_title="Kadowsella | 116 數位戰情室", page_icon="⚡", layout="wide")

def get_cycle_info():
    now = datetime.now()
    exam_date = datetime(2027, 1, 15)
    cycle_start = datetime(2026, 3, 1)
    days_left = (exam_date - now).days
    current_week = ((now - cycle_start).days // 7) + 1
    return {"week_num": max(1, current_week), "days_left": days_left, "season": "116 級巔峰戰役", "start_date": cycle_start}

CYCLE = get_cycle_info()
SUBJECTS = ["國文", "英文", "數學A","數學B","數學甲","數學乙", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

# ==========================================
# 2. 安全與資料庫功能
# ==========================================

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_db(sheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0)
        return df.fillna("無")
    except:
        return pd.DataFrame()

def save_to_db(new_data, sheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0)
        new_data['created_at'] = datetime.now().strftime("%Y-%m-%d")
        updated_df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
        conn.update(worksheet=sheet_name, data=updated_df)
        return True
    except: return False

# ==========================================
# 3. UI 視覺組件
# ==========================================

def inject_css():
    st.markdown("""
        <style>
        .card { border-radius: 15px; padding: 20px; background: var(--secondary-background-color); border: 1px solid var(--border-color); margin-bottom: 20px; border-left: 8px solid #6366f1; }
        .tag { background: #6366f1; color: white; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }
        .streak-badge { background: linear-gradient(135deg, #6366f1, #a855f7); color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; }
        .flashcard { height: 250px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #6366f1, #a855f7); color: white; border-radius: 20px; text-align: center; padding: 30px; font-size: 1.8em; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 4. 登入頁面 (新增訪客按鈕)
# ==========================================

def login_page():
    st.title("⚡ Kadowsella 116 登入")
    st.markdown("### 補習班沒教的數位複習法 | 116 級工程師邏輯戰情室")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        tab1, tab2 = st.tabs(["🔑 帳號登入", "📝 新生註冊"])
        with tab1:
            with st.form("login_form"):
                u = st.text_input("帳號")
                p = st.text_input("密碼", type="password")
                if st.form_submit_button("進入戰情室", use_container_width=True):
                    users_df = load_db("users")
                    if not users_df.empty:
                        user_record = users_df[(users_df['username'] == u) & (users_df['password'] == hash_password(p))]
                        if not user_record.empty:
                            st.session_state.logged_in = True
                            st.session_state.username = u
                            st.session_state.role = user_record.iloc[0]['role']
                            st.rerun()
                        else: st.error("帳號或密碼錯誤")
        
        with tab2:
            with st.form("reg_form"):
                new_u = st.text_input("設定帳號")
                new_p = st.text_input("設定密碼", type="password")
                if st.form_submit_button("完成註冊"):
                    users_df = load_db("users")
                    if not users_df.empty and new_u in users_df['username'].values:
                        st.warning("帳號已存在")
                    else:
                        if save_to_db({"username": new_u, "password": hash_password(new_p), "role": "student"}, "users"):
                            st.success("註冊成功！請登入。")

    with col2:
        st.markdown("---")
        st.write("🚀 **想先看看內容？**")
        if st.button("🚪 以訪客身分試用", use_container_width=True, type="primary"):
            st.session_state.logged_in = True
            st.session_state.username = "訪客"
            st.session_state.role = "guest"
            st.rerun()
        st.caption("註：訪客身分無法紀錄戰績與使用 AI 功能。")

# ==========================================
# 5. 主程式內容
# ==========================================

def main_app():
    inject_css()
    
    with st.sidebar:
        st.title(f"👋 你好, {st.session_state.username}")
        if st.session_state.role == "guest":
            st.warning("⚠️ 訪客模式")
        else:
            st.markdown(f"<div class='streak-badge'>🔥 116 戰力：Lv.1</div>", unsafe_allow_html=True)
        
        st.metric("距離 116 學測", f"{CYCLE['days_left']} Days")
        
        menu = ["📅 本週菜單", "🃏 閃卡複習", "🎲 隨機驗收", "🏆 戰力排行榜", "🤖 找學長姐聊聊"]
        if st.session_state.role == "admin":
            st.divider()
            menu.extend(["🔬 預埋考點", "🧪 考題開發"])
        
        choice = st.radio("導航", menu)
        if st.button("🚪 登出系統"):
            st.session_state.logged_in = False
            st.rerun()

    # 讀取資料
    c_df = load_db("Sheet1")
    l_df = load_db("leaderboard")

    # --- 頁面路由 ---
    if choice == "📅 本週菜單":
        st.title("🚀 116 級本週重點進度")
        if c_df.empty: st.info("資料庫建置中...")
        else:
            for _, r in c_df.tail(5).iterrows():
                st.markdown(f"<div class='card'><h3>{r['word']}</h3><p>{r['definition']}</p></div>", unsafe_allow_html=True)

    elif choice == "🎲 隨機驗收":
        st.title("🎲 隨機邏輯驗收")
        if not c_df.empty:
            row = c_df.sample(1).iloc[0]
            st.markdown(f"### 挑戰題目：{row['word']}")
            with st.expander("💡 顯示答案"): st.write(row['definition'])
            
            st.divider()
            if st.session_state.role == "guest":
                st.warning("💡 註冊帳號後即可提交戰績至全台排行榜！")
            else:
                with st.form("score_form"):
                    score = st.slider("掌握度 (%)", 0, 100, 80)
                    if st.form_submit_button("提交戰績"):
                        save_to_db({"username": st.session_state.username, "score": score, "subject": row['category']}, "leaderboard")
                        st.balloons(); st.success("戰績已同步！")

    elif choice == "🏆 戰力排行榜":
        st.title("🏆 116 戰力排行榜")
        if not l_df.empty:
            st.table(l_df.sort_values(by="score", ascending=False).head(10))
        else: st.info("尚無戰績。")

    elif choice == "🤖 找學長姐聊聊":
        st.title("🤖 找學霸學長姐聊聊")
        if st.session_state.role == "guest":
            st.error("🔒 AI 聊天功能僅限註冊會員使用。")
            st.info("註冊帳號是免費的，還能解鎖專屬序號！")
        else:
            st.write("學長姐正在連線中... (請串接 Gemini API)")

# ==========================================
# 6. 執行入口
# ==========================================

def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        login_page()
    else:
        main_app()

if __name__ == "__main__":
    main()
