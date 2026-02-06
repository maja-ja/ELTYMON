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

DISCORD_URL = st.secrets.get("DISCORD_LINK", "https://discord.gg/")
SUBJECTS = ["國文", "英文", "數學A","數學B","數學甲","數學乙", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

def get_cycle_info():
    now = datetime.now()
    exam_date = datetime(2027, 1, 15)
    cycle_start = datetime(2026, 3, 1)
    days_left = (exam_date - now).days
    current_week = ((now - cycle_start).days // 7) + 1
    return {"week_num": max(1, current_week), "days_left": days_left, "start_date": cycle_start}

CYCLE = get_cycle_info()

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
# 3. AI 引擎 (管理員上帝模式)
# ==========================================

def ai_call(system_instruction, user_input=""):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return None
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = model.generate_content(system_instruction + "\n\n" + user_input)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        return json.loads(match.group(0)) if match else response.text
    except: return None

def ai_decode_concept(input_text, subject):
    sys_prompt = f"""你現在是台灣高中補教名師。請針對「{subject}」的「{input_text}」進行拆解。
    請嚴格輸出 JSON：{{ "roots": "公式", "definition": "一句話定義", "breakdown": "重點拆解", "memory_hook": "諧音口訣", "native_vibe": "學長姐叮嚀", "star": 5 }}"""
    res = ai_call(sys_prompt)
    if isinstance(res, dict): res.update({"word": input_text, "category": subject})
    return res

def ai_generate_question(concept, subject):
    sys_prompt = f"""你現在是大考命題委員。請針對「{subject}」的「{concept}」出108課綱素養題。
    請嚴格輸出 JSON：{{ "concept": "{concept}", "subject": "{subject}", "q_type": "素養題", "listening_script": "無", "content": "題目全文", "answer_key": "解析", "translation": "無" }}"""
    return ai_call(sys_prompt)

# ==========================================
# 4. UI 視覺組件 (支援雙色模式)
# ==========================================

def inject_css():
    st.markdown(f"""
        <style>
        .card {{ border-radius: 15px; padding: 20px; background: var(--secondary-background-color); border: 1px solid var(--border-color); margin-bottom: 20px; border-left: 8px solid #6366f1; }}
        .tag {{ background: #6366f1; color: white; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }}
        .streak-badge {{ background: linear-gradient(135deg, #6366f1, #a855f7); color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; }}
        .admin-badge {{ background: #ef4444; color: white; padding: 2px 8px; border-radius: 5px; font-size: 0.7em; margin-left: 5px; }}
        .flashcard {{ height: 250px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #6366f1, #a855f7); color: white; border-radius: 20px; text-align: center; padding: 30px; font-size: 1.8em; }}
        </style>
    """, unsafe_allow_html=True)

def show_concept(row):
    st.markdown(f"""<div class="card"><span class="tag">{row['category']}</span> <span style="color:#f59e0b;">{'★' * int(row.get('star', 3))}</span>
    <h2 style="margin-top:10px;">{row['word']}</h2><p><b>💡 秒懂定義：</b>{row['definition']}</p></div>""", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"🧬 **核心邏輯**\n\n{row['roots']}")
        st.success(f"🧠 **記憶點**\n\n{row['memory_hook']}")
    with c2:
        st.warning(f"🚩 **學長姐雷區**\n\n{row['native_vibe']}")
        with st.expander("🔍 詳細拆解"): st.write(row['breakdown'])

# ==========================================
# 5. 頁面邏輯
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
                    user = users[(users['username'] == u) & (users['password'] == hash_password(p))]
                    if not user.empty:
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.session_state.role = user.iloc[0]['role']
                        st.rerun()
                    else: st.error("帳號或密碼錯誤")
        with tab2:
            with st.form("reg"):
                new_u = st.text_input("設定帳號")
                new_p = st.text_input("設定密碼", type="password")
                admin_code = st.text_input("管理員邀請碼 (學生免填)", type="password")
                if st.form_submit_button("完成註冊"):
                    role = "admin" if admin_code == st.secrets.get("ADMIN_PASSWORD") else "student"
                    if save_to_db({"username": new_u, "password": hash_password(new_p), "role": role}, "users"):
                        st.success(f"註冊成功！身分：{role}")
    with col2:
        st.markdown("---")
        st.write("🚀 **想先看看內容？**")
        if st.button("🚪 以訪客身分試用", use_container_width=True):
            st.session_state.logged_in = True
            st.session_state.username = "訪客"
            st.session_state.role = "guest"
            st.rerun()
        st.link_button("💬 加入 Discord 社群", DISCORD_URL, use_container_width=True)

def main_app():
    inject_css()
    with st.sidebar:
        role_tag = " <span class='admin-badge'>ADMIN</span>" if st.session_state.role == "admin" else ""
        st.markdown(f"### 👋 你好, {st.session_state.username}{role_tag}", unsafe_allow_html=True)
        if st.session_state.role != "guest":
            st.markdown(f"<div class='streak-badge'>🔥 116 戰力：Lv.1</div>", unsafe_allow_html=True)
        st.metric("距離 116 學測", f"{CYCLE['days_left']} Days")
        st.divider()
        menu = ["📅 本週菜單", "🃏 閃卡複習", "🎲 隨機驗收", "🏆 戰力排行榜", "🤖 找學長姐聊聊", "🍅 衝刺番茄鐘"]
        if st.session_state.role == "admin":
            st.subheader("🛠️ 管理員模式")
            menu.extend(["🔬 預埋考點", "🧪 考題開發"])
        choice = st.radio("導航", menu)
        if st.button("🚪 登出"): st.session_state.logged_in = False; st.rerun()

    c_df = load_db("Sheet1")
    q_df = load_db("questions")
    l_df = load_db("leaderboard")

    if choice == "📅 本週菜單":
        st.title("🚀 116 級本週重點進度")
        if not c_df.empty:
            for _, r in c_df.tail(5).iterrows(): show_concept(r)
        else: st.info("資料庫建置中...")

    elif choice == "🃏 閃卡複習":
        st.title("🃏 閃卡快速複習")
        if not c_df.empty:
            if 'card_idx' not in st.session_state: st.session_state.card_idx = 0
            row = c_df.iloc[st.session_state.card_idx % len(c_df)]
            flip = st.toggle("翻轉卡片")
            if not flip: st.markdown(f"<div class='flashcard'><b>{row['word']}</b></div>", unsafe_allow_html=True)
            else: st.markdown(f"<div class='flashcard' style='background:#10B981;'>{row['definition']}</div>", unsafe_allow_html=True)
            if st.button("下一題 ➡️"): st.session_state.card_idx += 1; st.rerun()

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
            else: st.warning("訪客無法提交戰績，請註冊帳號。")

    elif choice == "🏆 戰力排行榜":
        st.title("🏆 116 戰力排行榜")
        if not l_df.empty:
            st.table(l_df.sort_values(by="score", ascending=False).head(10))
            my_data = l_df[l_df['username'] == st.session_state.username]
            if not my_data.empty: st.metric("你的平均戰力", f"{my_data['score'].mean():.1f}%")
        else: st.info("尚無戰績。")

    elif choice == "🤖 找學長姐聊聊":
        st.title("🤖 找學霸學長姐聊聊")
        if st.session_state.role == "guest": st.error("🔒 AI 聊天僅限註冊會員。")
        else:
            if not st.session_state.get('chat_unlocked', False) and st.session_state.role != "admin":
                serial = st.text_input("🔑 輸入 116 專屬序號解鎖", type="password")
                if st.button("解鎖"):
                    if serial == st.secrets.get("CHAT_KEY", "KADOW116"): st.session_state.chat_unlocked = True; st.rerun()
            else:
                if prompt := st.chat_input("問點什麼..."):
                    st.chat_message("user").write(prompt)
                    res = ai_call("你是一位親切的台大學霸學長。", prompt)
                    st.chat_message("assistant").write(res)

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
# 6. 執行入口
# ==========================================

def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if not st.session_state.logged_in: login_page()
    else: main_app()

if __name__ == "__main__":
    main()
