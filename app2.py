import streamlit as st
import pandas as pd
import json, re, io, time, hashlib, urllib.parse
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
    return {"week_num": max(1, ((now - cycle_start).days // 7) + 1), "days_left": days_left, "start_date": cycle_start}

CYCLE = get_cycle_info()


# ==========================================
# 2. 安全與資料庫工具
# ==========================================

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()
def load_db(sheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0)
        df = df.fillna("無")
        if sheet_name == "users":
            df['ai_usage'] = pd.to_numeric(df['ai_usage'], errors='coerce').fillna(0)
        return df
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


def update_user_data(username, column, value):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="users", ttl=0)
        df.loc[df['username'] == username, column] = value
        conn.update(worksheet="users", data=df)
    except Exception as e:
        st.error(f"資料庫更新失敗: {e}")

# ==========================================
# 3. AI 引擎
# ==========================================
def ai_generate_question_from_db(db_row):
    """根據資料庫內容生成素養題目"""
    api_key = st.secrets.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    你現在是台灣大考中心命題委員。請根據以下資料出一題「108課綱素養導向」的題目。
    
    資料內容：
    概念：{db_row['word']} | 科目：{db_row['category']}
    定義：{db_row['definition']} | 核心邏輯：{db_row['roots']}
    
    要求輸出 JSON 格式：
    {{
        "concept": "{db_row['word']}",
        "subject": "{db_row['category']}",
        "q_type": "素養選擇題",
        "listening_script": "（若是英文科請提供對話腳本，其餘填無）",
        "content": "### 📝 情境描述\\n[設計一個生活情境]\\n\\n### ❓ 題目\\n[問題內容]\\n(A)選項\\n(B)選項\\n(C)選項\\n(D)選項",
        "answer_key": "【正確答案】\\n[答案]\\n\\n【防呆解析】\\n[用學長的口吻解釋為什麼選這個，並指出陷阱]",
        "translation": "（若是英文科請提供情境翻譯，其餘填無）"
    }}
    """
    try:
        response = model.generate_content(prompt)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except: return None
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
        .q-box { background: var(--secondary-background-color); padding: 20px; border-radius: 15px; border: 1px solid #10b981; margin-top: 10px; }
        .tag { background: #6366f1; color: white; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }
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
    
    # 讀取資料庫
    c_df = load_db("Sheet1")
    q_df = load_db("questions")
    users_df = load_db("users")
    
    user_data = users_df[users_df['username'] == st.session_state.username]
    try: ai_usage = int(float(user_data.iloc[0]['ai_usage'])) if not user_data.empty else 0
    except: ai_usage = 0

    with st.sidebar:
        st.title(f"👋 你好, {st.session_state.username}")
        st.metric("距離 116 學測", f"{CYCLE['days_left']} Days")
        st.divider()
        menu = ["📅 本週菜單", "🧪 AI 邏輯補給站", "📝 模擬演練", "🏆 戰力排行榜"]
        if st.session_state.role == "admin":
            menu.extend(["---", "🔬 預埋考點", "🧪 考題開發", "👤 使用者管理"])
        choice = st.radio("導航", menu)
        if st.button("🚪 登出"): st.session_state.logged_in = False; st.rerun()

    # --- 頁面路由 ---

    if choice == "📅 本週菜單":
        st.title("🚀 116 級本週重點進度")
        if not c_df.empty:
            for _, r in c_df.tail(5).iterrows():
                st.markdown(f'<div class="card"><h3>{r["word"]}</h3><p>{r["definition"]}</p></div>', unsafe_allow_html=True)

    elif choice == "📝 模擬演練":
        st.title("📝 素養模擬演練")
        if q_df.empty:
            st.info("目前題庫空空如也，請等待管理員出題。")
        else:
            concept_filter = st.selectbox("篩選測驗概念：", ["全部"] + q_df['concept'].unique().tolist())
            filtered_q = q_df if concept_filter == "全部" else q_df[q_df['concept'] == concept_filter]
            
            for _, row in filtered_q.iterrows():
                with st.container():
                    st.markdown(f"**【{row['subject']}】{row['concept']}**")
                    st.markdown(f'<div class="q-box">{row["content"]}</div>', unsafe_allow_html=True)
                    
                    with st.expander("🔓 查看答案與防呆解析"):
                        if row['translation'] != "無":
                            st.caption("🌐 中文翻譯")
                            st.write(row['translation'])
                        st.success(row['answer_key'])
                    st.divider()

    elif choice == "🧪 考題開發" and st.session_state.role == "admin":
        st.title("🧪 AI 考題開發 (上帝模式)")
        if c_df.empty:
            st.warning("請先去「預埋考點」新增概念，才能根據概念出題。")
        else:
            target_concept = st.selectbox("選擇要命題的概念：", c_df['word'].unique().tolist())
            if st.button("🪄 根據此概念生成素養題"):
                db_row = c_df[c_df['word'] == target_concept].iloc[0]
                with st.spinner("命題委員正在構思情境..."):
                    new_q = ai_generate_question_from_db(db_row)
                    if new_q:
                        st.session_state.temp_q = new_q
                        st.success("題目生成成功！請預覽下方內容。")
                    else: st.error("生成失敗")
            
            if "temp_q" in st.session_state:
                res = st.session_state.temp_q
                st.markdown("### 👀 題目預覽")
                st.write(res['content'])
                st.info(res['answer_key'])
                if st.button("💾 確認無誤，存入題庫"):
                    if save_to_db(res, "questions"):
                        st.success("已存入題庫！學生現在可以在「模擬演練」看到了。")
                        del st.session_state.temp_q
                        time.sleep(1); st.rerun()

    elif choice == "🔬 預埋考點" and st.session_state.role == "admin":
        # (保持原本的預埋考點邏輯...)
        st.title("🔬 AI 考點預埋")
        c1, c2 = st.columns([3, 1])
        inp = c1.text_input("輸入要拆解的概念", placeholder="例如：光電效應...")
        sub = c2.selectbox("所屬科目", SUBJECTS)

        if st.button("🚀 啟動 AI 深度解碼", use_container_width=True):
            if not inp:
                st.warning("請先輸入概念名稱！")
            else:
                with st.spinner(f"正在拆解「{inp}」..."):
                    sys_prompt = f"""
                    你現在是台灣高中名師。請針對「{sub}」的概念「{inp}」進行深度解析。
                    請嚴格遵守以下 JSON 格式輸出：
                    {{
                        "roots": "核心公式(LaTeX)或字源邏輯",
                        "definition": "108 課綱標準定義",
                        "breakdown": "條列式重點拆解(使用 \\n 換行)",
                        "memory_hook": "創意口訣或諧音聯想",
                        "native_vibe": "學長姐叮嚀",
                        "star": 5
                    }}
                    """
                    api_key = st.secrets.get("GEMINI_API_KEY")
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    try:
                        response = model.generate_content(sys_prompt)
                        res_text = response.text
                        match = re.search(r'\{.*\}', res_text, re.DOTALL)
                        if match:
                            res_data = json.loads(match.group(0))
                            res_data.update({"word": inp, "category": sub})
                            st.session_state.temp_concept = res_data
                        else: st.error("AI 回傳格式錯誤")
                    except Exception as e: st.error(f"AI 生成失敗: {e}")

        if "temp_concept" in st.session_state:
            res = st.session_state.temp_concept
            st.markdown("---")
            st.subheader("👀 生成內容預覽")
            with st.container():
                st.markdown(f"""
                <div class="card">
                    <span class="tag">{res['category']}</span> <span style="color:#f59e0b;">{'★' * int(res['star'])}</span>
                    <h2 style="margin-top:10px;">{res['word']}</h2>
                    <p><b>💡 秒懂定義：</b>{res['definition']}</p>
                </div>
                """, unsafe_allow_html=True)
                col_a, col_b = st.columns(2)
                with col_a:
                    st.info(f"🧬 **核心邏輯 / 公式**\n\n{res['roots']}")
                    st.success(f"🧠 **超強記憶點**\n\n{res['memory_hook']}")
                with col_b:
                    st.warning(f"🚩 **學長姐雷區叮嚀**\n\n{res['native_vibe']}")
                    with st.expander("🔍 詳細拆解", expanded=True): st.write(res['breakdown'])
            if st.button("💾 確認無誤，存入雲端資料庫", type="primary", use_container_width=True):
                if save_to_db(res, "Sheet1"):
                    st.balloons()
                    st.success(f"✅ 「{res['word']}」已成功埋入戰情室！")
                    del st.session_state.temp_concept
                    time.sleep(1)
                    st.rerun()
                else: st.error("存檔失敗")

# ==========================================
# 7. 執行入口
# ==========================================

def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if not st.session_state.logged_in: login_page()
    else: main_app()

if __name__ == "__main__":
    main()
