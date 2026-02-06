import streamlit as st
import pandas as pd
import json, re, io, time, hashlib
from datetime import datetime
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置
# ==========================================
st.set_page_config(page_title="Kadowsella | 116 數位戰情室", page_icon="⚡", layout="wide")

DISCORD_URL = st.secrets.get("DISCORD_LINK", "https://discord.gg/")
SUBJECTS = ["國文", "英文", "數學A","數學B","數學甲","數學乙", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

def get_cycle_info():
    now = datetime.now()
    exam_date = datetime(2027, 1, 15)
    cycle_start = datetime(2026, 3, 1)
    days_left = (exam_date - now).days
    return {"week_num": max(1, ((now - cycle_start).days // 7) + 1), "days_left": days_left}

CYCLE = get_cycle_info()

# ==========================================
# 2. 安全與資料庫工具
# ==========================================

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_db(sheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        return conn.read(worksheet=sheet_name, ttl=0).fillna("無")
    except: return pd.DataFrame()

def update_user_usage(username, new_count):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="users", ttl=0)
    df.loc[df['username'] == username, 'ai_usage'] = new_count
    conn.update(worksheet="users", data=df)

# ==========================================
# 3. AI 引擎 (根據資料庫內容進行「學長化」解釋)
# ==========================================

def ai_explain_from_db(db_row):
    """
    db_row: 來自 Sheet1 的一列資料 (Series)
    """
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "❌ API Key 缺失"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 餵給 AI 的背景資料
    context = f"""
    【學科概念】：{db_row['word']}
    【標準定義】：{db_row['definition']}
    【核心公式/邏輯】：{db_row['roots']}
    【重點拆解】：{db_row['breakdown']}
    【記憶口訣】：{db_row['memory_hook']}
    【學長姐叮嚀】：{db_row['native_vibe']}
    """
    
    sys_prompt = f"""
    你現在是台大學霸學長。請根據下方提供的【戰情室資料庫內容】，為學弟妹進行一場「深度邏輯教學」。
    
    教學要求：
    1. 內容必須嚴格基於提供的資料，不要過度發散。
    2. 語氣要親切、像在 Discord 語音頻道聊天一樣，但邏輯要極度清晰。
    3. 結構：
       - 先用白話文解釋這個概念在幹嘛。
       - 帶領學弟妹看懂核心公式/邏輯。
       - 強調資料庫中提到的「雷區」和「叮嚀」。
       - 最後用資料庫裡的「口訣」做結尾。
    
    資料內容如下：
    {context}
    """
    try:
        response = model.generate_content(sys_prompt)
        return response.text
    except: return "🤖 AI 學長目前斷線中，請稍後再試。"

# ==========================================
# 4. UI 組件
# ==========================================

def inject_css():
    st.markdown("""
        <style>
        .card { border-radius: 15px; padding: 20px; background: var(--secondary-background-color); border: 1px solid var(--border-color); margin-bottom: 20px; border-left: 8px solid #6366f1; }
        .quota-box { padding: 15px; border-radius: 10px; border: 1px solid #6366f1; text-align: center; margin-bottom: 20px; }
        .stButton>button { width: 100%; border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 5. 登入頁面
# ==========================================

def login_page():
    st.title("⚡ Kadowsella 116 登入")
    tab1, tab2 = st.tabs(["🔑 帳號登入", "📝 新生註冊"])
    with tab1:
        with st.form("login"):
            u = st.text_input("帳號")
            p = st.text_input("密碼", type="password")
            if st.form_submit_button("進入戰情室", use_container_width=True):
                users = load_db("users")
                user = users[(users['username'] == u) & (users['password'] == hash_password(p))]
                if not user.empty:
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.session_state.role = user.iloc[0]['role']
                    st.session_state.ai_usage = int(user.iloc[0].get('ai_usage', 0))
                    st.rerun()
                else: st.error("❌ 帳號或密碼錯誤")
    with tab2:
        with st.form("reg"):
            new_u = st.text_input("設定帳號")
            new_p = st.text_input("設定密碼", type="password")
            admin_code = st.text_input("管理員邀請碼 (學生免填)", type="password")
            if st.form_submit_button("完成註冊"):
                role = "admin" if admin_code == st.secrets.get("ADMIN_PASSWORD") else "student"
                conn = st.connection("gsheets", type=GSheetsConnection)
                df = conn.read(worksheet="users", ttl=0)
                new_user = pd.DataFrame([{"username": new_u, "password": hash_password(new_p), "role": role, "ai_usage": 0, "created_at": datetime.now().strftime("%Y-%m-%d")}])
                conn.update(worksheet="users", data=pd.concat([df, new_user], ignore_index=True))
                st.success("註冊成功！請登入。")

# ==========================================
# 6. 主程式內容
# ==========================================

d
def main_app():
    inject_css()
    
    # 同步 AI 次數
    users_df = load_db("users")
    current_user_data = users_df[users_df['username'] == st.session_state.username]
    if not current_user_data.empty:
        st.session_state.ai_usage = int(current_user_data.iloc[0]['ai_usage'])

    with st.sidebar:
        st.title(f"⚡ Kadowsella 116")
        st.metric("距離 116 學測", f"{CYCLE['days_left']} Days")
        st.divider()
        menu = ["📅 本週菜單", "🧪 AI 邏輯補給站", "🃏 閃卡複習", "🎲 隨機驗收", "🏆 戰力排行榜"]
        if st.session_state.role == "admin":
            menu.extend(["---", "👤 使用者管理", "🔬 預埋考點"])
        choice = st.radio("導航", menu)
        if st.button("🚪 登出"): st.session_state.logged_in = False; st.rerun()

    # 讀取資料庫
    c_df = load_db("Sheet1")

    if choice == "📅 本週菜單":
        st.title("🚀 116 級本週重點進度")
        if not c_df.empty:
            for _, r in c_df.tail(5).iterrows():
                st.markdown(f"""<div class="card"><h3>{r['word']}</h3><p>{r['definition']}</p></div>""", unsafe_allow_html=True)

    elif choice == "🧪 AI 邏輯補給站":
        st.title("🧪 AI 邏輯補給站 (資料庫驅動版)")
        
        MAX_USAGE = 10
        usage = st.session_state.ai_usage
        
        if st.session_state.role != "admin":
            st.markdown(f'<div class="quota-box"><h4>🔋 剩餘教學能量：{max(0, MAX_USAGE - usage)} / {MAX_USAGE}</h4></div>', unsafe_allow_html=True)

        if usage >= MAX_USAGE and st.session_state.role != "admin":
            st.error("🚨 能量耗盡！請聯繫學長補給。")
        else:
            st.info("💡 本功能會根據「戰情室資料庫」中的精華內容，由 AI 學長為你進行深度導讀。")
            
            if c_df.empty:
                st.warning("目前資料庫尚無內容，請等待管理員預埋考點。")
            else:
                # 讓學生從資料庫已有的清單中選擇 (確保 AI 有資料可依據)
                concept_list = c_df['word'].unique().tolist()
                selected_concept = st.selectbox("請選擇你想秒懂的概念：", ["--- 請選擇 ---"] + concept_list)
                
                if selected_concept != "--- 請選擇 ---":
                    # 抓取該列資料
                    db_row = c_df[c_df['word'] == selected_concept].iloc[0]
                    
                    if st.button("🚀 啟動學長深度教學"):
                        with st.spinner(f"正在根據資料庫解析「{selected_concept}」..."):
                            # 呼叫 AI 進行解釋
                            explanation = ai_explain_from_db(db_row)
                            st.markdown("---")
                            st.markdown(explanation)
                            
                            # 扣除次數
                            if st.session_state.role != "admin":
                                new_count = usage + 1
                                update_user_usage(st.session_state.username, new_count)
                                st.session_state.ai_usage = new_count
                                # 不使用 rerun 以免畫面跳掉，讓學生看完
                else:
                    st.write("👆 請從上方選單選擇一個概念。")


    elif choice == "👤 使用者管理" and st.session_state.role == "admin":
        st.title("👤 使用者權限與能量管理")
        u_df = load_db("users")
        for i, row in u_df.iterrows():
            if row['role'] == "admin": continue
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.write(f"**{row['username']}**")
            c2.write(f"已用能量：{row['ai_usage']}")
            if c3.button("能量補滿", key=f"reset_{i}"):
                update_user_usage(row['username'], 0)
                st.success(f"已重置 {row['username']} 的能量！")
                time.sleep(1); st.rerun()

    elif choice == "🎲 隨機驗收":
        st.title("🎲 隨機邏輯驗收")
        if not c_df.empty:
            row = c_df.sample(1).iloc[0]
            st.markdown(f"### 挑戰題目：{row['word']}")
            with st.expander("💡 顯示答案"): st.write(row['definition'])
            if st.session_state.role != "guest":
                with st.form("score"):
                    score = st.slider("掌握度 (%)", 0, 100, 80)
                    if st.form_submit_button("提交戰績"):
                        save_to_db({"username": st.session_state.username, "score": score, "subject": row['category']}, "leaderboard")
                        st.balloons(); st.success("戰績已同步！")

    elif choice == "🏆 戰力排行榜":
        st.title("🏆 116 戰力排行榜")
        if not l_df.empty:
            st.table(l_df.sort_values(by="score", ascending=False).head(10))
        else: st.info("尚無戰績。")

    elif choice == "🔬 預埋考點" and st.session_state.role == "admin":
        st.title("🔬 AI 考點自動拆解")
        inp = st.text_input("輸入概念")
        sub = st.selectbox("科目", SUBJECTS)
        if st.button("🚀 執行 AI 解碼"):
            res = ai_decode_concept(inp, sub)
            if res: st.session_state.temp_c = res; st.write(res)
        if "temp_c" in st.session_state:
            if st.button("💾 存入 Sheet1"): save_to_db(st.session_state.temp_c, "Sheet1"); del st.session_state.temp_c; st.rerun()

    elif choice == "🧪 考題開發" and st.session_state.role == "admin":
        st.title("🧪 AI 素養題生成")
        q_inp = st.text_input("命題核心")
        q_sub = st.selectbox("科目", SUBJECTS, key="q_sub")
        if st.button("🪄 命題"):
            res = ai_generate_question(q_inp, q_sub)
            if res: st.session_state.temp_q = res; st.write(res)
        if "temp_q" in st.session_state:
            if st.button("💾 存入 questions"): save_to_db(st.session_state.temp_q, "questions"); del st.session_state.temp_q; st.rerun()

    elif choice == "🍅 衝刺番茄鐘":
        st.title("🍅 衝刺番茄鐘")
        mins = st.number_input("設定分鐘", value=25, step=5)
        if st.button("🔥 開始專注"):
            ph = st.empty()
            for t in range(mins * 60, 0, -1):
                m, s = divmod(t, 60); ph.metric("剩餘時間", f"{m:02d}:{s:02d}"); time.sleep(1)
            st.balloons(); st.success("太強了！")

# ==========================================
# 7. 執行入口
# ==========================================

def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if not st.session_state.logged_in: login_page()
    else: main_app()

if __name__ == "__main__":
    main()
