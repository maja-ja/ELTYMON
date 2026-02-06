import streamlit as st
import pandas as pd
import json, re, io, time, hashlib, urllib.parse
from datetime import datetime
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置 & 116 戰情邏輯
# ==========================================
st.set_page_config(page_title="Kadowsella | 116 數位戰情室", page_icon="⚡", layout="wide")

DISCORD_URL = st.secrets.get("DISCORD_LINK", "https://discord.gg/")
SUBJECTS = ["國文", "英文", "數學A","數學B","數學甲","數學乙", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

def get_cycle_info():
    now = datetime.now()
    exam_date = datetime(2027, 1, 15)
    cycle_start = datetime(2026, 3, 1)
    days_left = (exam_date - now).days
    return {"week_num": max(1, ((now - cycle_start).days // 7) + 1), "days_left": days_left, "start_date": cycle_start}

CYCLE = get_cycle_info()

# ==========================================
# 2. 安全與資料庫工具 (含自動補欄位防呆)
# ==========================================

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_db(sheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0)
        df = df.fillna("無")
        # 防呆：確保 users 表格必要的欄位存在
        if sheet_name == "users":
            if 'ai_usage' not in df.columns: df['ai_usage'] = 0
            if 'can_chat' not in df.columns: df['can_chat'] = "FALSE"
        return df
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

def update_user_data(username, column, value):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="users", ttl=0)
        df.loc[df['username'] == username, column] = value
        conn.update(worksheet="users", data=df)
    except Exception as e:
        st.error(f"資料庫更新失敗: {e}")

# ==========================================
# 3. AI 引擎 (資料庫驅動教學)
# ==========================================

def ai_explain_from_db(db_row):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "❌ 找不到 API Key"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    context = f"""
    概念：{db_row['word']} | 定義：{db_row['definition']}
    公式邏輯：{db_row['roots']} | 重點：{db_row['breakdown']}
    口訣：{db_row['memory_hook']} | 叮嚀：{db_row['native_vibe']}
    """
    prompt = f"你是一位台大學霸學長，請根據以下資料進行深度教學，語氣要親切且邏輯清晰：\n{context}"
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except: return "🤖 AI 學長目前斷線中。"

# ==========================================
# 4. UI 組件
# ==========================================

def inject_css():
    st.markdown("""
        <style>
        .card { border-radius: 15px; padding: 20px; background: var(--secondary-background-color); border: 1px solid var(--border-color); margin-bottom: 20px; border-left: 8px solid #6366f1; }
        .tag { background: #6366f1; color: white; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }
        .streak-badge { background: linear-gradient(135deg, #6366f1, #a855f7); color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; }
        .quota-box { padding: 15px; border-radius: 10px; border: 1px solid #6366f1; text-align: center; margin-bottom: 20px; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 5. 登入頁面
# ==========================================

def login_page():
    st.title("⚡ Kadowsella 116 登入")
    col1, col2 = st.columns([2, 1])
    with col1:
        tab1, tab2 = st.tabs(["🔑 帳號登入", "📝 新生註冊"])
        with tab1:
            with st.form("login"):
                u = st.text_input("帳號")
                p = st.text_input("密碼", type="password")
                if st.form_submit_button("進入戰情室", use_container_width=True):
                    users = load_db("users")
                    if not users.empty:
                        user = users[(users['username'] == u) & (users['password'] == hash_password(p))]
                        if not user.empty:
                            st.session_state.logged_in = True
                            st.session_state.username = u
                            st.session_state.role = user.iloc[0]['role']
                            st.rerun()
                        else: st.error("❌ 帳號或密碼錯誤")
        with tab2:
            with st.form("reg"):
                new_u = st.text_input("設定帳號")
                new_p = st.text_input("設定密碼", type="password")
                admin_code = st.text_input("管理員邀請碼 (學生免填)", type="password")
                if st.form_submit_button("完成註冊"):
                    role = "admin" if admin_code == st.secrets.get("ADMIN_PASSWORD") else "student"
                    if save_to_db({"username": new_u, "password": hash_password(new_p), "role": role, "ai_usage": 0, "can_chat": "FALSE"}, "users"):
                        st.success("註冊成功！請登入。")
    with col2:
        st.markdown("---")
        if st.button("🚪 以訪客身分試用", use_container_width=True):
            st.session_state.logged_in = True
            st.session_state.username = "訪客"
            st.session_state.role = "guest"
            st.rerun()
        st.link_button("💬 加入 Discord 社群", DISCORD_URL, use_container_width=True)

# ==========================================
# 6. 主程式內容
# ==========================================

def main_app():
    inject_css()
    
    # 同步使用者數據
    users_df = load_db("users")
    user_data = users_df[users_df['username'] == st.session_state.username]
    ai_usage = int(user_data.iloc[0]['ai_usage']) if not user_data.empty else 0

    with st.sidebar:
        st.title(f"👋 你好, {st.session_state.username}")
        if st.session_state.role != "guest":
            st.markdown(f"<div class='streak-badge'>🔥 116 戰力：Lv.1</div>", unsafe_allow_html=True)
        st.metric("距離 116 學測", f"{CYCLE['days_left']} Days")
        st.divider()
        menu = ["📅 本週菜單", "🧪 AI 邏輯補給站", "🃏 閃卡複習", "🎲 隨機驗收", "🏆 戰力排行榜"]
        if st.session_state.role == "admin":
            menu.extend(["---", "👤 使用者管理", "🔬 預埋考點"])
        choice = st.radio("導航", menu)
        if st.button("🚪 登出"): st.session_state.logged_in = False; st.rerun()

    c_df = load_db("Sheet1")

    if choice == "📅 本週菜單":
        st.title("🚀 116 級本週重點進度")
        if not c_df.empty:
            for _, r in c_df.tail(5).iterrows():
                st.markdown(f'<div class="card"><h3>{r["word"]}</h3><p>{r["definition"]}</p></div>', unsafe_allow_html=True)
        else: st.info("資料庫建置中...")

    elif choice == "🧪 AI 邏輯補給站":
        st.title("🧪 AI 邏輯補給站")
        MAX_USAGE = 10
        
        if st.session_state.role == "guest":
            st.warning("🔒 訪客無法使用 AI 教學，請註冊帳號。")
        else:
            if st.session_state.role != "admin":
                st.markdown(f'<div class="quota-box"><h4>🔋 剩餘教學能量：{max(0, MAX_USAGE - ai_usage)} / {MAX_USAGE}</h4></div>', unsafe_allow_html=True)

            if ai_usage >= MAX_USAGE and st.session_state.role != "admin":
                st.error("🚨 能量耗盡！請聯繫學長補給。")
                st.link_button("💬 前往 Discord 找學長", DISCORD_URL)
            else:
                if c_df.empty: st.warning("資料庫尚無內容。")
                else:
                    concept = st.selectbox("選擇你想秒懂的概念：", ["--- 請選擇 ---"] + c_df['word'].unique().tolist())
                    if concept != "--- 請選擇 ---" and st.button("🚀 啟動學長深度教學"):
                        db_row = c_df[c_df['word'] == concept].iloc[0]
                        res = ai_explain_from_db(db_row)
                        st.markdown("---")
                        st.markdown(res)
                        if st.session_state.role != "admin":
                            update_user_data(st.session_state.username, "ai_usage", ai_usage + 1)
                            st.rerun()

    elif choice == "🏆 戰力排行榜":
        st.title("🏆 116 戰力排行榜")
        l_df = load_db("leaderboard")
        if not l_df.empty:
            st.table(l_df.sort_values(by="score", ascending=False).head(10))
        else: st.info("尚無戰績。")

    elif choice == "👤 使用者管理" and st.session_state.role == "admin":
        st.title("👤 使用者管理")
        for i, row in users_df.iterrows():
            if row['role'] == "admin": continue
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.write(f"**{row['username']}**")
            c2.write(f"已用能量：{row['ai_usage']}")
            if c3.button("能量補滿", key=f"reset_{i}"):
                update_user_data(row['username'], "ai_usage", 0)
                st.rerun()

    elif choice == "🔬 預埋考點" and st.session_state.role == "admin":
        st.title("🔬 AI 考點預埋")
        inp = st.text_input("輸入概念")
        sub = st.selectbox("科目", SUBJECTS)
        if st.button("🚀 生成"):
            # 這裡調用之前的 ai_decode_concept 邏輯 (略)
            st.write("AI 生成中...")

# ==========================================
# 7. 執行入口
# ==========================================

def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if not st.session_state.logged_in: login_page()
    else: main_app()

if __name__ == "__main__":
    main()
