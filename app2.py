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
        return conn.read(worksheet=sheet_name, ttl=0).fillna("無")
    except: return pd.DataFrame()

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
# 3. AI 引擎 (支援 JSON 工具與純文字聊天)
# ==========================================

def ai_call(system_instruction, user_input=""):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "❌ 找不到 API Key"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = model.generate_content(system_instruction + "\n\n" + user_input)
        res_text = response.text
        if "JSON" in system_instruction:
            match = re.search(r'\{.*\}', res_text, re.DOTALL)
            return json.loads(match.group(0)) if match else None
        return res_text
    except: return "🤖 AI 暫時斷線..."
def check_and_update_quota(username, role, limit=10):
    """檢查並更新使用者的 AI 額度"""
    if role == "admin": return True, 0 # 管理員無限體力
    
    u_df = load_db("users")
    if u_df.empty: return False, 0
    
    idx = u_df.index[u_df['username'] == username].tolist()[0]
    last_date = str(u_df.at[idx, 'last_ai_date'])
    count = int(u_df.at[idx, 'ai_count'])
    today = datetime.now().strftime("%Y-%m-%d")
    
    if last_date != today:
        # 新的一天，重置次數
        u_df.at[idx, 'last_ai_date'] = today
        u_df.at[idx, 'ai_count'] = 1
        st.connection("gsheets", type=GSheetsConnection).update(worksheet="users", data=u_df)
        return True, 1
    else:
        if count >= limit:
            return False, count
        else:
            # 增加次數
            u_df.at[idx, 'ai_count'] = count + 1
            st.connection("gsheets", type=GSheetsConnection).update(worksheet="users", data=u_df)
            return True, count + 1
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
# 4. UI 視覺組件
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

# ==========================================
# 5. 登入與權限管理
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
                        st.session_state.can_chat = str(user.iloc[0].get('can_chat', "FALSE")) == "TRUE"
                        st.rerun()
                    else: st.error("❌ 帳號或密碼錯誤")
        with tab2:
            with st.form("reg"):
                new_u = st.text_input("設定帳號")
                new_p = st.text_input("設定密碼", type="password")
                admin_code = st.text_input("管理員邀請碼 (學生免填)", type="password")
                if st.form_submit_button("完成註冊"):
                    role = "admin" if admin_code == st.secrets.get("ADMIN_PASSWORD") else "student"
                    can_chat = "TRUE" if role == "admin" else "FALSE"
                    if save_to_db({"username": new_u, "password": hash_password(new_p), "role": role, "can_chat": can_chat}, "users"):
                        st.success(f"註冊成功！身分：{role}。請聯繫管理員開通 AI 權限。")
    with col2:
        st.markdown("---")
        st.write("🚀 **訪客預覽**")
        if st.button("🚪 以訪客身分試用", use_container_width=True):
            st.session_state.logged_in = True
            st.session_state.username = "訪客"
            st.session_state.role = "guest"
            st.session_state.can_chat = False
            st.rerun()
        st.link_button("💬 加入 Discord 社群", DISCORD_URL, use_container_width=True)

# ==========================================
# 6. 主程式內容
# ==========================================

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
            menu.extend(["🔬 預埋考點", "🧪 考題開發", "👤 使用者管理"])
        choice = st.radio("導航", menu)
        if st.button("🚪 登出"): st.session_state.logged_in = False; st.rerun()

    c_df = load_db("Sheet1")
    q_df = load_db("questions")
    l_df = load_db("leaderboard")

    if choice == "📅 本週菜單":
        st.title("🚀 116 級本週重點進度")
        if not c_df.empty:
            for _, r in c_df.tail(5).iterrows():
                with st.container():
                    st.markdown(f"""<div class="card"><span class="tag">{r['category']}</span><h3>{r['word']}</h3><p>{r['definition']}</p></div>""", unsafe_allow_html=True)
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
            if st.session_state.role not in ["guest"]:
                with st.form("score"):
                    score = st.slider("掌握度 (%)", 0, 100, 80)
                    if st.form_submit_button("提交戰績"):
                        save_to_db({"username": st.session_state.username, "score": score, "subject": row['category']}, "leaderboard")
                        st.balloons(); st.success("戰績已同步！")
            else: st.warning("訪客無法提交戰績。")

    elif choice == "🏆 戰力排行榜":
        st.title("🏆 116 戰力排行榜")
        if not l_df.empty:
            st.table(l_df.sort_values(by="score", ascending=False).head(10))
        else: st.info("尚無戰績。")

    elif choice == "🤖 找學長姐聊聊":
        st.title("🤖 找學霸學長姐聊聊")
        
        # 1. 權限檢查 (原本的授權制)
        is_auth = (st.session_state.role == "admin") or (st.session_state.get('can_chat', False))
        if not is_auth:
            st.error("🔒 權限未開通")
            st.stop()

        # 2. 體力值檢查 (防止無限吃)
        # 這裡設定每天限額 10 次
        daily_limit = 10
        can_use, current_count = check_and_update_quota(st.session_state.username, st.session_state.role, limit=daily_limit)
        
        if not can_use:
            st.error(f"❌ 今日體力已耗盡 ({current_count}/{daily_limit})")
            st.warning("AI 運算很貴的，學長姐也要休息，明天再來吧！")
            st.stop()
        
        st.caption(f"🔋 今日剩餘額度：{daily_limit - current_count} 次")

        
        if "messages" not in st.session_state: st.session_state.messages = []
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]): st.write(msg["content"])
        if prompt := st.chat_input("問點什麼..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            res = ai_call("你是一位親切的台大學霸學長，擅長用邏輯簡化知識。", prompt)
            st.session_state.messages.append({"role": "assistant", "content": res})
            with st.chat_message("assistant"): st.write(res)

    elif choice == "👤 使用者管理" and st.session_state.role == "admin":
        st.title("👤 使用者權限管理")
        u_df = load_db("users")
        if not u_df.empty:
            for i, row in u_df.iterrows():
                if row['role'] == "admin": continue
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.write(f"**{row['username']}**")
                status = "✅ 已開通" if str(row['can_chat']) == "TRUE" else "❌ 未開通"
                c2.write(status)
                if str(row['can_chat']) != "TRUE":
                    if c3.button("授權", key=f"auth_{i}"):
                        u_df.at[i, 'can_chat'] = "TRUE"
                        st.connection("gsheets", type=GSheetsConnection).update(worksheet="users", data=u_df)
                        st.success(f"已開通 {row['username']}"); time.sleep(1); st.rerun()

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
