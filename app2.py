import streamlit as st
import pandas as pd
import json, re, io, time
from datetime import datetime, timedelta
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
from gtts import gTTS

# ==========================================
# 1. 核心配置 & 賽季邏輯
# ==========================================
st.set_page_config(page_title="Kadowsella | 108課綱戰情室", page_icon="⚡", layout="wide")

SUBJECTS = ["國文", "英文", "數學A","數學B","數學甲","數學乙", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

def get_cycle_info():
    now = datetime.now()
    current_year = now.year
    # 每年 3/1 開訓
    cycle_start = datetime(current_year - 1, 3, 1) if now.month < 3 else datetime(current_year, 3, 1)
    # 每年 1/15 學測
    exam_date = datetime(current_year, 1, 15)
    if now > exam_date: exam_date = datetime(current_year + 1, 1, 15)
    
    days_left = (exam_date - now).days
    current_week = ((now - cycle_start).days // 7) + 1
    return {
        "week_num": max(1, current_week), 
        "days_left": days_left, 
        "season": f"{cycle_start.year} 戰役",
        "start_date": cycle_start
    }

CYCLE = get_cycle_info()

# ==========================================
# 2. AI 引擎
# ==========================================

def ai_call(system_instruction, user_input=""):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "請在 Secrets 中設定 GEMINI_API_KEY"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = model.generate_content(system_instruction + "\n\n" + user_input)
        return response.text
    except: return "AI 目前離線中..."

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

# ==========================================
# 3. 工具函式
# ==========================================

def generate_audio(text):
    try:
        tts = gTTS(text=text, lang='en')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except: return None

def load_db(sheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0)
        return df.fillna("無")
    except: return pd.DataFrame()

def save_to_db(new_data, sheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0)
        new_data['created_at'] = datetime.now().strftime("%Y-%m-%d")
        updated_df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
        conn.update(worksheet=sheet_name, data=updated_df)
        st.toast(f"✅ {sheet_name} 同步成功！")
    except: st.error("同步失敗，請檢查資料表權限。")

# ==========================================
# 4. UI 視覺組件 (支援雙色模式)
# ==========================================

def inject_css():
    st.markdown("""
        <style>
        /* 使用 Streamlit 原生變數以支援雙色模式 */
        .card { 
            border-radius: 15px; 
            padding: 20px; 
            background: var(--secondary-background-color); 
            border: 1px solid var(--border-color);
            margin-bottom: 20px; 
            border-left: 8px solid #6366f1; 
        }
        .tag { background: #6366f1; color: white; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }
        .flashcard { 
            height: 250px; display: flex; align-items: center; justify-content: center; 
            background: linear-gradient(135deg, #6366f1, #a855f7); color: white; 
            border-radius: 20px; text-align: center; padding: 30px; font-size: 1.8em; 
        }
        .streak-badge { background: linear-gradient(135deg, #fbbf24, #f59e0b); color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; text-align: center; }
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

# ==========================================
# 5. 主程式頁面
# ==========================================

def main():
    inject_css()
    
    # --- 資料預加載與 Bug 修復 ---
    c_df = load_db("Sheet1")
    q_df = load_db("questions")

    def get_w(d):
        try: 
            dt = datetime.strptime(str(d), "%Y-%m-%d")
            return ((dt - CYCLE['start_date']).days // 7) + 1
        except: return 0

    # 核心修復：確保 'w' 欄位一定存在
    if not c_df.empty:
        c_df['w'] = c_df['created_at'].apply(get_w)
    else:
        c_df = pd.DataFrame(columns=['word', 'category', 'roots', 'definition', 'breakdown', 'memory_hook', 'native_vibe', 'star', 'created_at', 'w'])

    if not q_df.empty:
        q_df['w'] = q_df['created_at'].apply(get_w)
    else:
        q_df = pd.DataFrame(columns=['concept', 'subject', 'q_type', 'content', 'listening_script', 'answer_key', 'translation', 'created_at', 'w'])

    # --- Sidebar ---
    with st.sidebar:
        st.title("⚡ Kadowsella")
        st.markdown(f"<div class='streak-badge'>🔥 學習戰力：連續 3 天</div>", unsafe_allow_html=True)
        st.metric("距離學測", f"{CYCLE['days_left']} Days", f"Week {CYCLE['week_num']}")
        
        menu = ["📅 本週菜單", "🃏 閃卡複習", "📝 模擬演練", "🤖 找學長姐聊聊", "🍅 衝刺番茄鐘", "📚 歷史庫存"]
        
        is_admin = False
        with st.expander("🔑 管理員入口"):
            pwd = st.text_input("密碼", type="password")
            if pwd == st.secrets.get("ADMIN_PASSWORD"):
                is_admin = True
                menu.extend(["🔬 預埋考點", "🧪 考題開發"])
        
        choice = st.radio("導航", menu)
        if st.button("🔄 刷新數據"): st.cache_data.clear(); st.rerun()

    # 權限過濾
    v_c = c_df if is_admin else c_df[c_df['w'] <= CYCLE['week_num']]
    v_q = q_df if is_admin else q_df[q_df['w'] <= CYCLE['week_num']]

    # --- 頁面路由 ---

    if choice == "📅 本週菜單":
        st.title(f"🚀 第 {CYCLE['week_num']} 週重點進度")
        this_week = v_c[v_c['w'] == CYCLE['week_num']]
        if this_week.empty: st.info("本週還沒更新，先去複習之前的吧！")
        else:
            for _, r in this_week.iterrows(): show_concept(r)

    elif choice == "🃏 閃卡複習":
        st.title("🃏 閃卡快速複習")
        if not v_c.empty:
            if 'card_idx' not in st.session_state: st.session_state.card_idx = 0
            row = v_c.iloc[st.session_state.card_idx % len(v_c)]
            flip = st.toggle("翻轉卡片看定義")
            if not flip:
                st.markdown(f"<div class='flashcard'><b>{row['word']}</b></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='flashcard' style='background:#10B981;'>{row['definition']}</div>", unsafe_allow_html=True)
            if st.button("下一題 ➡️"):
                st.session_state.card_idx += 1
                st.rerun()
        else: st.warning("目前沒有卡片。")

    elif choice == "📝 模擬演練":
        st.title("✍️ 素養題庫演練")
        if v_q.empty: st.info("題庫正在趕工中...")
        else:
            for _, r in v_q.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{r['subject']} | {r['concept']}**")
                    if r['subject'] == "英文" and r['listening_script'] != "無":
                        audio = generate_audio(r['listening_script'])
                        if audio: st.audio(audio)
                    st.markdown(r['content'])
                    with st.expander("查看解析"):
                        st.success(r['answer_key'])

    elif choice == "🤖 找學長姐聊聊":
        st.title("🤖 找學霸學長姐聊聊")
        
        # Discord 邀請區塊
        with st.container(border=True):
            st.subheader("💬 加入我們的 Discord 討論群")
            if is_admin:
                new_dc = st.text_input("管理員：請輸入 Discord 邀請連結", value=st.session_state.get('dc_link', "https://discord.gg/"))
                st.session_state.dc_link = new_dc
            
            current_dc = st.session_state.get('dc_link', "https://discord.gg/尚未設定")
            st.markdown(f"👉 [點我進入 Discord 交流群]({current_dc})")

        # Chat 區塊
        if "messages" not in st.session_state:
            st.session_state.messages = [{"role": "assistant", "content": "嘿！我是你的台大學長，哪科卡住了？"}]
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])
        if prompt := st.chat_input("輸入問題..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)
            response = ai_call("你是一位親切的台大學霸學長，會用簡單例子解釋高中課程。", prompt)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.chat_message("assistant").write(response)

    elif choice == "🍅 衝刺番茄鐘":
        st.title("🍅 衝刺番茄鐘")
        mins = st.number_input("設定分鐘", value=25, step=5)
        if st.button("🔥 開始專注"):
            ph = st.empty()
            for t in range(mins * 60, 0, -1):
                m, s = divmod(t, 60)
                ph.metric("剩餘時間", f"{m:02d}:{s:02d}")
                time.sleep(1)
            st.balloons()
            st.success("太強了！")

    elif choice == "📚 歷史庫存":
        st.title("📚 歷史考點全紀錄")
        if not v_c.empty:
            for w in sorted(v_c['w'].unique(), reverse=True):
                with st.expander(f"第 {w} 週考點"):
                    for _, r in v_c[v_c['w'] == w].iterrows(): show_concept(r)

    elif choice == "🔬 預埋考點" and is_admin:
        st.title("🔬 AI 考點生成")
        inp = st.text_input("輸入概念")
        sub = st.selectbox("科目", SUBJECTS)
        if st.button("🚀 生成並存檔"):
            res = ai_decode_concept(inp, sub)
            if res: show_concept(res); save_to_db(res, "Sheet1")

if __name__ == "__main__":
    main()
