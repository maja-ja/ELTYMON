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
    # 針對 116 級：2027/1/15 學測
    exam_date = datetime(2027, 1, 15)
    cycle_start = datetime(2026, 3, 1)
    days_left = (exam_date - now).days
    current_week = ((now - cycle_start).days // 7) + 1
    return {
        "week_num": max(1, current_week), 
        "days_left": days_left, 
        "season": "116 級巔峰戰役",
        "start_date": cycle_start
    }

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
        # 如果讀取失敗，回傳帶有預設欄位的空 DataFrame
        cols = {
            "Sheet1": ['word', 'category', 'roots', 'definition', 'breakdown', 'memory_hook', 'native_vibe', 'star', 'created_at'],
            "questions": ['concept', 'subject', 'q_type', 'content', 'listening_script', 'answer_key', 'translation', 'created_at'],
            "leaderboard": ['username', 'score', 'subject', 'created_at'],
            "users": ['username', 'password', 'role', 'created_at']
        }
        return pd.DataFrame(columns=cols.get(sheet_name, []))

def save_to_db(new_data, sheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0)
        new_data['created_at'] = datetime.now().strftime("%Y-%m-%d")
        updated_df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
        conn.update(worksheet=sheet_name, data=updated_df)
        return True
    except:
        return False

# ==========================================
# 3. AI 與 工具函式
# ==========================================

def ai_call(system_instruction, user_input=""):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "請設定 API KEY"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = model.generate_content(system_instruction + "\n\n" + user_input)
        return response.text
    except: return "AI 腦袋過熱中..."

def generate_audio(text):
    try:
        tts = gTTS(text=text, lang='en')
        fp = io.BytesIO()
        tts.write_to_fp(fp); fp.seek(0)
        return fp
    except: return None

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
# 4. 頁面組件
# ==========================================

def login_page():
    st.title("⚡ Kadowsella 116 登入")
    st.markdown("### 補習班沒教的數位複習法 | 116 級工程師邏輯戰情室")
    
    tab1, tab2 = st.tabs(["🔑 登入", "📝 註冊"])
    
    with tab1:
        with st.form("login_form"):
            u = st.text_input("帳號 (Username)")
            p = st.text_input("密碼 (Password)", type="password")
            if st.form_submit_button("進入戰情室", use_container_width=True):
                users_df = load_db("users")
                if not users_df.empty:
                    user_record = users_df[(users_df['username'] == u) & (users_df['password'] == hash_password(p))]
                    if not user_record.empty:
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.session_state.role = user_record.iloc[0]['role']
                        st.success("登入成功！")
                        time.sleep(0.5)
                        st.rerun()
                    else: st.error("帳號或密碼錯誤")
                else: st.error("系統尚未初始化")

    with tab2:
        with st.form("reg_form"):
            new_u = st.text_input("設定帳號")
            new_p = st.text_input("設定密碼", type="password")
            role_code = st.text_input("管理員邀請碼 (學生免填)", type="password")
            if st.form_submit_button("完成註冊"):
                users_df = load_db("users")
                if not users_df.empty and new_u in users_df['username'].values:
                    st.warning("此帳號已被註冊")
                else:
                    role = "admin" if role_code == st.secrets.get("ADMIN_PASSWORD") else "student"
                    if save_to_db({"username": new_u, "password": hash_password(new_p), "role": role}, "users"):
                        st.success("註冊成功！請切換至登入頁面。")
                    else: st.error("註冊失敗")

def main_app():
    inject_css()
    
    # 側邊欄
    with st.sidebar:
        st.title(f"👋 你好, {st.session_state.username}")
        st.markdown(f"<div class='streak-badge'>🔥 116 戰力：Lv.1</div>", unsafe_allow_html=True)
        st.metric("距離 116 學測", f"{CYCLE['days_left']} Days", f"Week {CYCLE['week_num']}")
        
        menu = ["📅 本週菜單", "🃏 閃卡複習", "🎲 隨機驗收", "🏆 戰力排行榜", "🤖 找學長姐聊聊", "🍅 衝刺番茄鐘"]
        if st.session_state.role == "admin":
            st.divider()
            menu.extend(["🔬 預埋考點", "🧪 考題開發"])
        
        choice = st.radio("導航", menu)
        if st.button("🚪 登出系統"):
            st.session_state.logged_in = False
            st.rerun()

    # 讀取資料並修復週次 Bug
    c_df = load_db("Sheet1")
    q_df = load_db("questions")
    l_df = load_db("leaderboard")

    def get_w(d):
        try: return ((datetime.strptime(str(d), "%Y-%m-%d") - CYCLE['start_date']).days // 7) + 1
        except: return 0
    
    for df in [c_df, q_df]:
        if not df.empty: df['w'] = df['created_at'].apply(get_w)
        else: df['w'] = []

    # 權限過濾
    v_c = c_df if st.session_state.role == "admin" else c_df[c_df['w'] <= CYCLE['week_num']] if not c_df.empty else c_df

    # --- 頁面路由 ---
    if choice == "📅 本週菜單":
        st.title("🚀 116 級本週重點進度")
        this_week = v_c[v_c['w'] == CYCLE['week_num']] if not v_c.empty else pd.DataFrame()
        if this_week.empty: st.info("本週進度尚未解鎖。")
        else:
            for _, r in this_week.iterrows():
                st.markdown(f"<div class='card'><h3>{r['word']}</h3><p>{r['definition']}</p></div>", unsafe_allow_html=True)

    elif choice == "🎲 隨機驗收":
        st.title("🎲 隨機邏輯驗收")
        if not v_c.empty:
            row = v_c.sample(1).iloc[0]
            st.markdown(f"### 挑戰題目：{row['word']}")
            with st.expander("💡 顯示答案"): st.write(row['definition'])
            
            # 銜接排行榜
            st.divider()
            with st.form("score_form"):
                st.write(f"戰士：{st.session_state.username}")
                score = st.slider("掌握度 (%)", 0, 100, 80)
                if st.form_submit_button("提交戰績"):
                    save_to_db({"username": st.session_state.username, "score": score, "subject": row['category']}, "leaderboard")
                    st.balloons(); st.success("戰績已同步！")
        else: st.warning("資料庫空空如也。")

    elif choice == "🏆 戰力排行榜":
        st.title("🏆 116 戰力排行榜")
        if not l_df.empty:
            st.subheader("🔥 全台 Top 10")
            st.table(l_df.sort_values(by="score", ascending=False).head(10))
            my_data = l_df[l_df['username'] == st.session_state.username]
            if not my_data.empty:
                st.metric("你的平均戰力", f"{my_data['score'].mean():.1f}%")
        else: st.info("尚無戰績。")

    elif choice == "🤖 找學長姐聊聊":
        st.title("🤖 找學霸學長姐聊聊")
        # Discord 邀請
        st.info("💬 [點我加入 Discord 討論群](https://discord.gg/yourlink)")
        
        if not st.session_state.get('chat_unlocked', False) and st.session_state.role != "admin":
            serial = st.text_input("🔑 輸入 116 專屬序號解鎖對話", type="password")
            if st.button("解鎖"):
                if serial == st.secrets.get("CHAT_KEY", "KADOW116"):
                    st.session_state.chat_unlocked = True; st.rerun()
        else:
            if prompt := st.chat_input("問點什麼..."):
                st.chat_message("user").write(prompt)
                res = ai_call("你是一位親切的台大學霸學長。", prompt)
                st.chat_message("assistant").write(res)

    elif choice == "🍅 衝刺番茄鐘":
        st.title("🍅 衝刺番茄鐘")
        mins = st.number_input("設定分鐘", value=25, step=5)
        if st.button("🔥 開始專注"):
            ph = st.empty()
            for t in range(mins * 60, 0, -1):
                m, s = divmod(t, 60); ph.metric("剩餘時間", f"{m:02d}:{s:02d}"); time.sleep(1)
            st.balloons(); st.success("太強了！")

# ==========================================
# 5. 執行入口
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
