import streamlit as st
import pandas as pd
import json, re, io, time, urllib.parse
from datetime import datetime, timedelta
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
from gtts import gTTS

# ==========================================
# 1. 核心配置 & 116 戰情邏輯
# ==========================================
st.set_page_config(page_title="Kadowsella | 116 數位戰情室", page_icon="⚡", layout="wide")

SUBJECTS = ["國文", "英文", "數學A","數學B","數學甲","數學乙", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

def get_cycle_info():
    now = datetime.now()
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

# ==========================================
# 2. AI 引擎 & 工具
# ==========================================

def ai_call(system_instruction, user_input=""):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return None
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = model.generate_content(system_instruction + "\n\n" + user_input)
        return response.text
    except: return None

def ai_decode_concept(input_text, subject):
    sys_prompt = f"""
    你現在是台灣高中補教名師。請針對「{subject}」的「{input_text}」進行拆解。
    請嚴格輸出 JSON：
    {{
        "roots": "核心公式(LaTeX)或邏輯底層",
        "definition": "用一句話講完重點",
        "breakdown": "拆解成3個重點(用\\n換行)",
        "memory_hook": "超強諧音口訣或迷因聯想",
        "native_vibe": "學長姐叮嚀：這題在學測怎麼考？哪裡是雷區？",
        "star": "考頻星等(1-5)"
    }}
    """
    res_text = ai_call(sys_prompt)
    match = re.search(r'\{.*\}', res_text, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        data.update({"word": input_text, "category": subject})
        return data
    return None

def ai_generate_question(concept, subject):
    sys_prompt = f"""
    你現在是台灣大考中心命題委員。請針對「{subject}」的「{concept}」出一份108課綱素養模擬題。
    如果是英文，必須包含 listening_script (聽力腳本)。
    請嚴格輸出 JSON：
    {{
        "concept": "{concept}",
        "subject": "{subject}",
        "q_type": "108課綱素養題",
        "listening_script": "（英文聽力腳本，其餘填無）",
        "content": "### 📝 情境描述\\n[描述情境]\\n\\n### ❓ 題目\\n[題目與選項]",
        "answer_key": "正確答案與『防呆解析』",
        "translation": "（英文翻譯，其餘填無）"
    }}
    """
    res_text = ai_call(sys_prompt)
    match = re.search(r'\{.*\}', res_text, re.DOTALL)
    return json.loads(match.group(0)) if match else None

def generate_audio(text):
    try:
        tts = gTTS(text=text, lang='en')
        fp = io.BytesIO()
        tts.write_to_fp(fp); fp.seek(0)
        return fp
    except: return None

# ==========================================
# 3. 資料庫邏輯
# ==========================================

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
        st.toast(f"🚀 數據已同步至 {sheet_name}")
    except: st.error("同步失敗")

# ==========================================
# 4. UI 視覺組件 (支援雙色模式)
# ==========================================

def inject_css():
    st.markdown("""
        <style>
        .card { 
            border-radius: 15px; padding: 20px; 
            background: var(--secondary-background-color); 
            border: 1px solid var(--border-color);
            margin-bottom: 20px; border-left: 8px solid #6366f1; 
        }
        .tag { background: #6366f1; color: white; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }
        .flashcard { 
            height: 250px; display: flex; align-items: center; justify-content: center; 
            background: linear-gradient(135deg, #6366f1, #a855f7); color: white; 
            border-radius: 20px; text-align: center; padding: 30px; font-size: 1.8em; 
        }
        .streak-badge { background: linear-gradient(135deg, #6366f1, #a855f7); color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; }
        .share-btn { 
            display: inline-block; background: #06C755; color: white !important; 
            padding: 8px 15px; border-radius: 10px; text-decoration: none; font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

def show_concept(row):
    with st.container():
        st.markdown(f"""
        <div class="card">
            <span class="tag">{row['category']}</span> <span style="color:#f59e0b;">{'★' * int(row.get('star', 3))}</span>
            <h2 style="margin-top:10px;">{row['word']}</h2>
            <p><b>💡 秒懂定義：</b>{row['definition']}</p>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.info(f"🧬 **核心邏輯 / 公式**\n\n{row['roots']}")
            st.success(f"🧠 **超強記憶點**\n\n{row['memory_hook']}")
        with c2:
            st.warning(f"🚩 **學長姐雷區叮嚀**\n\n{row['native_vibe']}")
            with st.expander("🔍 詳細拆解"): st.write(row['breakdown'])

def show_question(row):
    with st.container(border=True):
        st.markdown(f"<span class='tag'>{row['subject']}</span> **{row['concept']}**", unsafe_allow_html=True)
        if row['subject'] == "英文" and row['listening_script'] != "無":
            audio = generate_audio(row['listening_script'])
            if audio: st.audio(audio)
        st.markdown(row['content'])
        with st.expander("🔓 查看解析"):
            if row['translation'] != "無": st.write(row['translation'])
            st.success(row['answer_key'])

def show_share_section(title, content):
    text = f"【Kadowsella 116 戰情室】這題誰會？\n\n{title}\n{content[:50]}..."
    encoded_text = urllib.parse.quote(text)
    line_url = f"https://line.me/R/msg/text/?{encoded_text}"
    st.markdown(f'<a href="{line_url}" target="_blank" class="share-btn">📲 分享至 Line 群組求救</a>', unsafe_allow_html=True)

# ==========================================
# 5. 主程式
# ==========================================

def main():
    inject_css() # 注入支援雙色模式的 CSS
    
    # --- 1. 初始化 Session State ---
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'role' not in st.session_state:
        st.session_state.role = "student"
    if 'chat_unlocked' not in st.session_state:
        st.session_state.chat_unlocked = False
    if 'card_idx' not in st.session_state:
        st.session_state.card_idx = 0

    # --- 2. 登入邏輯控制 ---
    if not st.session_state.logged_in:
        login_page() # 顯示登入/註冊頁面
    else:
        # --- 3. 正式進入戰情室 (main_app) ---
        
        # A. 預加載資料庫
        c_df = load_db("Sheet1")      # 知識點
        q_df = load_db("questions")   # 題庫
        l_df = load_db("leaderboard") # 排行榜
        
        # B. 週次邏輯處理 (防止 KeyError)
        def get_w(d):
            try: 
                dt = datetime.strptime(str(d), "%Y-%m-%d")
                return ((dt - CYCLE['start_date']).days // 7) + 1
            except: return 0

        for df in [c_df, q_df]:
            if not df.empty:
                df['w'] = df['created_at'].apply(get_w)
            else:
                # 若為空則建立空欄位避免報錯
                df['w'] = []

        # C. Sidebar 側邊欄設計
        with st.sidebar:
            st.title(f"⚡ Kadowsella 116")
            st.markdown(f"**戰士：{st.session_state.username}**")
            st.markdown(f"<div class='streak-badge'>🔥 116 戰力：Lv.1</div>", unsafe_allow_html=True)
            st.metric("距離 116 學測", f"{CYCLE['days_left']} Days", f"Week {CYCLE['week_num']}")
            
            # 根據權限調整選單
            menu = ["📅 本週菜單", "🃏 閃卡複習", "🎲 隨機驗收", "🏆 戰力排行榜", "📝 模擬演練", "🤖 找學長姐聊聊", "🍅 衝刺番茄鐘"]
            if st.session_state.role == "admin":
                st.divider()
                st.subheader("🛠️ 管理員模式")
                menu.extend(["🔬 預埋考點", "🧪 考題開發"])
            
            choice = st.radio("功能導航", menu)
            
            if st.button("🚪 登出系統", use_container_width=True):
                st.session_state.logged_in = False
                st.rerun()

        # D. 頁面路由邏輯
        
        if choice == "📅 本週菜單":
            st.title(f"🚀 第 {CYCLE['week_num']} 週重點進度")
            st.caption("補習班沒教的數位複習法：用工程師邏輯模組化知識。")
            this_week = c_df[c_df['w'] == CYCLE['week_num']] if not c_df.empty else pd.DataFrame()
            if this_week.empty:
                st.info("本週進度尚未解鎖，先去複習歷史庫存吧！")
            else:
                for _, r in this_week.iterrows(): show_concept(r)

        elif choice == "🎲 隨機驗收":
            st.title("🎲 隨機邏輯驗收")
            if not c_df.empty:
                row = c_df.sample(1).iloc[0]
                st.markdown(f"### 挑戰題目：{row['word']}")
                with st.expander("💡 點擊顯示邏輯定義"):
                    st.write(row['definition'])
                    st.success(f"🧠 記憶掛鉤：{row['memory_hook']}")
                
                # 一鍵分享功能
                show_share_section(row['word'], row['definition'])
                
                # 銜接排行榜：自動帶入登入帳號
                st.divider()
                st.subheader("🏆 登錄戰力榜")
                with st.form("score_form"):
                    st.write(f"登錄帳號：**{st.session_state.username}**")
                    score = st.slider("這題的掌握度 (%)", 0, 100, 80)
                    if st.form_submit_button("提交戰績"):
                        save_to_db({
                            "username": st.session_state.username, 
                            "score": score, 
                            "subject": row['category']
                        }, "leaderboard")
                        st.balloons()
                        st.success("戰績已同步至全台排行榜！")
            else:
                st.warning("目前題庫沒有資料。")

        elif choice == "🏆 戰力排行榜":
            st.title("🏆 116 戰力排行榜")
            if not l_df.empty:
                # 全台前 10 名
                st.subheader("🔥 全台 Top 10 巔峰榜")
                top_10 = l_df.sort_values(by="score", ascending=False).head(10)
                st.table(top_10[['username', 'subject', 'score', 'created_at']])
                
                # 個人戰績分析
                st.divider()
                my_data = l_df[l_df['username'] == st.session_state.username]
                if not my_data.empty:
                    avg_v = my_data['score'].mean()
                    st.metric("你的平均戰力值", f"{avg_v:.1f} %", f"已挑戰 {len(my_data)} 題")
            else:
                st.info("目前尚無戰績，快去隨機驗收刷一波！")

        elif choice == "🤖 找學長姐聊聊":
            st.title("🤖 找學霸學長姐聊聊")
            # 序號管制
            if not st.session_state.chat_unlocked and st.session_state.role != "admin":
                st.warning("🔒 此功能需輸入 116 專屬序號開啟")
                serial = st.text_input("輸入序號", type="password")
                if st.button("解鎖對話"):
                    if serial == st.secrets.get("CHAT_KEY", "KADOW116"):
                        st.session_state.chat_unlocked = True
                        st.rerun()
            else:
                # 已解鎖或管理員：顯示對話
                if "messages" not in st.session_state: st.session_state.messages = []
                for msg in st.session_state.messages: st.chat_message(msg["role"]).write(msg["content"])
                if prompt := st.chat_input("問點什麼..."):
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    st.chat_message("user").write(prompt)
                    res = ai_call("你是一位親切的台大學霸學長，擅長用邏輯簡化知識。", prompt)
                    st.session_state.messages.append({"role": "assistant", "content": res})
                    st.chat_message("assistant").write(res)

        elif choice == "🔬 預埋考點" and st.session_state.role == "admin":
            st.title("🔬 管理員：AI 考點預埋")
            inp = st.text_input("輸入要拆解的概念")
            sub = st.selectbox("科目", SUBJECTS)
            if st.button("🚀 執行 AI 解碼"):
                with st.spinner("名師正在拆解中..."):
                    res = ai_decode_concept(inp, sub)
                    if res:
                        show_concept(res)
                        if st.button("💾 確認存入雲端"):
                            save_to_db(res, "Sheet1")
                            st.rerun()

        # ... 其他功能 (閃卡、番茄鐘、模擬演練) 依此類推 ...

if __name__ == "__main__":
    main()
