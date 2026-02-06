import streamlit as st
import pandas as pd
import json, re, io
from datetime import datetime, timedelta
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
from gtts import gTTS

# ==========================================
# 1. 核心配置 & 賽季邏輯
# ==========================================
st.set_page_config(page_title="Kadowsella | 無限賽季版", page_icon="♾️", layout="wide")

SUBJECTS = ["國文", "英文", "數學A","數學B","數學C","數學甲","數學乙", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

def get_cycle_info():
    now = datetime.now()
    current_year = now.year
    if now.month < 3:
        cycle_start = datetime(current_year - 1, 3, 1)
    else:
        cycle_start = datetime(current_year, 3, 1)

    exam_date = datetime(current_year, 1, 15)
    if now > exam_date:
        exam_date = datetime(current_year + 1, 1, 15)
        
    lockdown_date = exam_date - timedelta(days=10)
    days_left = (exam_date - now).days
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

# ==========================================
# 2. AI 與 語音 工具
# ==========================================

def generate_audio(text):
    """將文字轉為語音流"""
    try:
        tts = gTTS(text=text, lang='en')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        st.error(f"語音合成失敗: {e}")
        return None

def ai_call(system_instruction):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("❌ 找不到 API_KEY")
        return None
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = model.generate_content(system_instruction)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except Exception as e:
        st.error(f"AI 錯誤: {e}")
        return None

def ai_decode_concept(input_text, subject):
    prompt = f"""
    你現在是台灣高中升學考試名師。針對「{subject}」的「{input_text}」進行深度解析。
    請嚴格輸出 JSON：
    {{
        "roots": "LaTeX 公式或核心邏輯",
        "definition": "108 課綱標準定義",
        "breakdown": "條列式重點拆解(用\\n換行)",
        "memory_hook": "口訣或聯想",
        "native_vibe": "考試陷阱提醒"
    }}
    公式請用單個 $ 包裹。
    """
    res = ai_call(prompt)
    if res:
        res.update({"word": input_text, "category": subject})
    return res

def ai_generate_question(concept, subject):
    prompt_context = ""
    if subject == "國文":
        prompt_context = "包含：1.單選、2.多選、3.非選題。"
    elif subject == "英文":
        prompt_context = "包含：1.聽力測驗腳本(listening_script)、2.閱讀短文與題目。"
    else:
        prompt_context = "包含兩道情境素養題。"

    prompt = f"""
    針對「{subject}」的「{concept}」出題。{prompt_context}
    請嚴格輸出 JSON：
    {{
        "concept": "{concept}",
        "subject": "{subject}",
        "q_type": "綜合測驗",
        "listening_script": "（僅限英文聽力內容，其餘填無）",
        "content": "題目全文(用\\n換行)",
        "answer_key": "正確答案與詳細解析",
        "translation": "（僅限英文提供翻譯，其餘填無）"
    }}
    """
    return ai_call(prompt)

# ==========================================
# 3. 資料庫邏輯
# ==========================================

def load_db(sheet_name="Sheet1"):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0)
        return df.fillna("無")
    except:
        return pd.DataFrame()

def save_to_db(new_data, sheet_name="Sheet1"):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        existing_df = conn.read(worksheet=sheet_name, ttl=0)
        new_data['created_at'] = datetime.now().strftime("%Y-%m-%d")
        updated_df = pd.concat([existing_df, pd.DataFrame([new_data])], ignore_index=True)
        conn.update(worksheet=sheet_name, data=updated_df)
        st.toast(f"✅ 已同步至雲端 {sheet_name}")
    except Exception as e:
        st.error(f"寫入失敗: {e}")

# ==========================================
# 4. UI 顯示組件
# ==========================================

def inject_custom_css():
    st.markdown("""
        <style>
            .subject-tag { background: #3B82F6; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
            .q-box { background: #F1F5F9; padding: 20px; border-radius: 10px; border-left: 5px solid #10B981; margin-bottom: 20px; color: #1E293B; }
        </style>
    """, unsafe_allow_html=True)

def show_concept_card(row):
    st.markdown(f"### <span class='subject-tag'>{row['category']}</span> {row['word']}", unsafe_allow_html=True)
    with st.container(border=True):
        st.write("**🧬 重點拆解**")
        st.write(row['breakdown'])
    c1, c2 = st.columns(2)
    with c1: st.info(f"💡 **定義**\n\n{row['definition']}")
    with c2: st.success(f"📌 **核心公式/字源**\n\n{row['roots']}")

def show_question_card(row):
    with st.container(border=True):
        st.subheader(f"📝 {row['subject']} | {row['concept']}")
        
        # 英聽播放條
        if row['subject'] == "英文" and row['listening_script'] != "無":
            st.write("🎧 **聽力播放**")
            audio_data = generate_audio(row['listening_script'])
            if audio_data: st.audio(audio_data, format="audio/mp3")
        
        st.markdown(row['content'])
        with st.expander("查看解析與翻譯"):
            if row['translation'] != "無":
                st.write("**【翻譯】**")
                st.write(row['translation'])
            st.success(f"**【答案解析】**\n\n{row['answer_key']}")

# ==========================================
# 5. 主程式
# ==========================================

def main():
    inject_custom_css()
    is_admin = False
    
    # Sidebar
    with st.sidebar:
        st.title("♾️ Kadowsella")
        st.caption(f"當前賽季: {CYCLE['season_label']}")
        st.metric("距離學測", f"{CYCLE['days_left']} 天")
        
        menu = ["📅 本週菜單", "🛡️ 歷史回顧", "📝 模擬演練", "🎲 隨機抽題"]
        
        with st.expander("🔑 管理員"):
            if st.text_input("Password", type="password") == st.secrets.get("ADMIN_PASSWORD"):
                is_admin = True
                menu.extend(["🔬 預埋考點", "🧪 考題開發"])
        
        choice = st.radio("功能導航", menu)
        if st.button("🔄 強制刷新數據"): st.cache_data.clear(); st.rerun()

    # 資料讀取
    concept_df = load_db("Sheet1")
    question_df = load_db("questions")

    def get_week(date_str):
        try:
            dt = datetime.strptime(str(date_str), "%Y-%m-%d")
            return ((dt - CYCLE["start_date"]).days // 7) + 1
        except: return 0

    # 學生權限過濾
    if not concept_df.empty:
        concept_df['week'] = concept_df['created_at'].apply(get_week)
        v_concepts = concept_df if is_admin else concept_df[concept_df['week'] <= CYCLE['week_num']]
    else: v_concepts = pd.DataFrame()

    if not question_df.empty:
        question_df['week'] = question_df['created_at'].apply(get_week)
        v_questions = question_df if is_admin else question_df[question_df['week'] <= CYCLE['week_num']]
    else: v_questions = pd.DataFrame()

    # --- 頁面路由 ---
    if choice == "📅 本週菜單":
        st.title(f"第 {CYCLE['week_num']} 週訓練任務")
        this_week = v_concepts[v_concepts['week'] == CYCLE['week_num']]
        if this_week.empty: st.info("本週尚無新考點。")
        else:
            for _, r in this_week.iterrows(): show_concept_card(r)

    elif choice == "🛡️ 歷史回顧":
        st.title("🛡️ 知識庫存")
        if not v_concepts.empty:
            weeks = sorted(v_concepts['week'].unique(), reverse=True)
            for w in weeks:
                with st.expander(f"📂 第 {w} 週回顧"):
                    for _, r in v_concepts[v_concepts['week'] == w].iterrows(): show_concept_card(r)

    elif choice == "📝 模擬演練":
        st.title("📝 素養模擬演練")
        if v_questions.empty: st.info("題庫建置中...")
        else:
            for _, r in v_questions.iterrows(): show_question_card(r)

    elif choice == "🎲 隨機抽題":
        if not v_concepts.empty:
            if st.button("🎲 換一題"): st.rerun()
            show_concept_card(v_concepts.sample(1).iloc[0])

    elif choice == "🔬 預埋考點" and is_admin:
        st.title("🔬 AI 考點填裝")
        c1, c2 = st.columns([3, 1])
        inp = c1.text_input("輸入概念")
        sub = c2.selectbox("科目", SUBJECTS)
        if st.button("🚀 執行解碼"):
            res = ai_decode_concept(inp, sub)
            if res:
                show_concept_card(res)
                save_to_db(res, "Sheet1")

    elif choice == "🧪 考題開發" and is_admin:
        st.title("🧪 AI 模擬試題生成")
        c1, c2 = st.columns([3, 1])
        q_inp = c1.text_input("輸入命題核心")
        q_sub = c2.selectbox("科目", SUBJECTS, key="q_sub")
        if st.button("🪄 生成題目"):
            q_res = ai_generate_question(q_inp, q_sub)
            if q_res:
                st.session_state.temp_q = q_res
        
        if "temp_q" in st.session_state:
            show_question_card(st.session_state.temp_q)
            if st.button("💾 確認存入題庫"):
                save_to_db(st.session_state.temp_q, "questions")
                del st.session_state.temp_q
                st.rerun()

if __name__ == "__main__":
    main()
