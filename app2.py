import streamlit as st
import pandas as pd
import json, re, io, time, hashlib, urllib.parse
from datetime import datetime
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置 & 116 戰情邏輯
# ==========================================
st.set_page_config(
    page_title="Kadowsella | 116 數位戰情室",
    page_icon="⚡",
    layout="wide",
    menu_items={
        'About': "# Kadowsella 116\n這是一個專屬授權系統，嚴禁未經授權之複製。"
    }
)

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

        # 強制修復欄位缺失問題
        if sheet_name == "users":
            expected_cols = ['username', 'password', 'role', 'can_chat', 'ai_usage', 'created_at']
            for col in expected_cols:
                if col not in df.columns: df[col] = 0 if col == 'ai_usage' else "無"
            df['ai_usage'] = pd.to_numeric(df['ai_usage'], errors='coerce').fillna(0)

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

def update_user_data(username, column, value):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="users", ttl=0)
        df.loc[df['username'] == username, column] = value
        conn.update(worksheet="users", data=df)
    except: pass

# ==========================================
# 3. AI 引擎
# ==========================================
def clean_json_string(json_str):
    """
    處理 AI 回傳 JSON 時常見的 LaTeX 反斜線報錯問題
    """
    # 1. 處理掉可能存在的 Markdown 程式碼區塊標籤
    # 修正：將 json.replace 改為 json_str.replace
    json_str = json_str.replace("```json", "").replace("```", "").strip()

    # 2. 核心修復：將 LaTeX 常見的反斜線進行轉義處理
    # 這裡使用正則表達式，尋找後面不是跟著 (n, r, t, b, f, u, ", \) 的反斜線並補上一個反斜線
    # 但最簡單暴力且有效的方法是針對 LaTeX 關鍵字處理，或直接對所有反斜線做初步處理
    fixed_str = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', json_str)

    return fixed_str
def ai_generate_question_from_db(db_row):
    """
    根據資料庫的一列資料生成素養題目
    db_row: 來自 Sheet1 的資料 (Series 或 Dict)
    """
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("❌ 找不到 API Key")
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash') # 使用 gemini-1.5-flash

    # 建立針對 108 課綱的命題 Prompt
    prompt = f"""
    你現在是台灣大考中心命題委員。請根據以下資料出一題「108課綱素養導向」的選擇題。

    【參考資料】：
    概念：{db_row['word']}
    科目：{db_row['category']}
    定義：{db_row['definition']}
    核心邏輯：{db_row['roots']}

    【重要規範】：
    1. 所有的數學符號、座標、公式、根號，必須使用 LaTeX 格式並用單個錢字號包裹。例如：$(0,0)$、$x^2$。
    2. 題目必須包含「情境描述」與「問題內容」。

    請嚴格輸出 JSON 格式：
    {{
        "concept": "{db_row['word']}",
        "subject": "{db_row['category']}",
        "q_type": "素養選擇題",
        "listening_script": "無",
        "content": "### 📝 情境描述\\n[情境文字]\\n\\n### ❓ 題目\\n[題目文字]\\n(A) [選項]\\n(B) [選項]\\n(C) [選項]\\n(D) [選項]",
        "answer_key": "【正確答案】\\n[答案]\\n\\n【防呆解析】\\n[解析內容]",
        "translation": "無"
    }}
    """

    try:
        response = model.generate_content(prompt)
        res_text = response.text
        # 提取 JSON 內容
        match = re.search(r'\{.*\}', res_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            st.error("AI 回傳格式非 JSON，請重試。")
            return None
    except Exception as e:
        st.error(f"AI 出題發生錯誤: {e}")
        return None
def ai_call(system_instruction, user_input="", temp=0.7):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return None
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash') # 使用 gemini-1.5-flash

    try:
        response = model.generate_content(
            system_instruction + "\n\n" + user_input,
            generation_config=genai.types.GenerationConfig(temperature=temp)
        )
        res_text = response.text

        if "JSON" in system_instruction:
            # 提取 { ... } 之間的內容
            match = re.search(r'\{.*\}', res_text, re.DOTALL)
            if match:
                raw_json = match.group(0)
                # --- 關鍵修復步驟 ---
                clean_json = clean_json_string(raw_json)
                try:
                    # 使用 strict=False 可以容忍一些不標準的換行
                    return json.loads(clean_json, strict=False)
                except json.JSONDecodeError as e:
                    # 如果還是失敗，嘗試最後一次：直接把所有單反斜線換成雙反斜線
                    try:
                        last_resort = raw_json.replace('\\', '\\\\').replace('\\\\"', '\\"')
                        return json.loads(last_resort, strict=False)
                    except:
                        st.error(f"JSON 解析最終失敗: {e}")
                        return None
        return res_text
    except Exception as e:
        st.error(f"AI 呼叫失敗: {e}")
        return None

def ai_decode_concept(input_text, subject):
    sys_prompt = f"""【重要】在輸出 JSON 時，所有的反斜線 \ 必須寫成 \\ (例如 \\frac, \\sqrt)，以符合標準 JSON 格式，否則解析會失敗。你現在是台大醫學系學霸，請針對「{subject}」的概念「{input_text}」進行深度拆解。
    請嚴格輸出 JSON：{{ "roots": "核心公式(LaTeX)", "definition": "一句話定義", "breakdown": "重點拆解", "memory_hook": "諧音口訣", "native_vibe": "學長姐叮嚀", "star": 5 }}"""
    res = ai_call(sys_prompt, temp=0.5) # 邏輯用低溫
    if isinstance(res, dict): res.update({"word": input_text, "category": subject})
    return res

def ai_generate_social_post(concept_data):
    sys_prompt = f"""【重要】在輸出 JSON 時，所有的反斜線 \ 必須寫成 \\ (例如 \\frac, \\sqrt)，以符合標準 JSON 格式，否則解析會失敗。你是一個在 Threads 上發瘋的 116 學測技術宅。你剛用 AI 拆解了「{concept_data['word']}」，覺得 Temp 0 的邏輯美到哭。
    請寫一篇極度厭世、多表情符號、吸引戰友留言『飛翔』的脆文。多用💀、謝了、116。"""
    return ai_call(sys_prompt, str(concept_data), temp=1.5) # 社群文用高溫

def ai_explain_from_db(db_row):
    context = f"概念：{db_row['word']} | 定義：{db_row['definition']} | 公式：{db_row['roots']} | 口訣：{db_row['memory_hook']}"
    prompt = f"【重要】在輸出 JSON 時，所有的反斜線 \ 必須寫成 \\ (例如 \\frac, \\sqrt)，以符合標準 JSON 格式，否則解析會失敗。你是一位台大學霸學長，請根據以下資料進行深度教學，語氣要親切且邏輯清晰：\n{context}"
    return ai_call(prompt, temp=0.7)


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
# 4.5. 新增：PDF 匯出功能 ( now accepts filename )
# ==========================================
def add_pdf_export_button(filename="116級戰情室-文件.pdf"):
    """在頁面注入一個懸浮按鈕，用於觸發 PDF 下載功能，可自訂檔名。"""
    # Safely encode filename for JavaScript string literal
    js_filename = json.dumps(filename, ensure_ascii=False)

    pdf_export_html = f"""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        #export-button {{ /* Use double braces to escape f-string for CSS */
            visibility: hidden; /* 初始隱藏，等待頁面載入完成 */
            position: fixed;
            bottom: 25px;
            right: 25px;
            background-color: #6366f1;
            color: white;
            border: none;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        #export-button:hover {{
            background-color: #4f46e5;
        }}
    </style>

    <button id="export-button" title="下載本頁為 PDF">📄</button>

    <script>
        // 確保在 Streamlit 完全渲染後再執行
        window.addEventListener('load', function () {{
            const exportButton = document.getElementById('export-button');
            const pdfFilename = {js_filename}; // Dynamically set filename

            if (exportButton) {{
                exportButton.style.visibility = 'visible'; // 載入完成後顯示按鈕

                exportButton.addEventListener('click', function () {{
                    // 暫時隱藏按鈕和側邊欄，避免出現在 PDF 中
                    exportButton.style.visibility = 'hidden';
                    const sidebar = document.querySelector('[data-testid="stSidebar"]');
                    if (sidebar) {{
                        sidebar.style.display = 'none';
                    }}

                    // 選取要匯出的主要內容區域
                    const element = document.querySelector('[data-testid="stAppViewContainer"]');

                    const options = {{
                        margin: [10, 10, 10, 10], // 上、左、下、右邊距 (mm)
                        filename: pdfFilename, // Use the dynamic filename
                        image: {{ type: 'jpeg', quality: 0.98 }},
                        html2canvas: {{
                            scale: 2, // 提高解析度
                            useCORS: true,
                            logging: false
                        }},
                        jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                    }};

                    // 執行匯出並在完成後恢復介面
                    html2pdf().from(element).set(options).save().then(() => {{
                        exportButton.style.visibility = 'visible';
                        if (sidebar) {{
                            sidebar.style.display = 'block';
                        }}
                    }}).catch((error) => {{
                        console.error('PDF 生成失敗:', error);
                        // 即使失敗也要確保介面恢復
                        exportButton.style.visibility = 'visible';
                        if (sidebar) {{
                            sidebar.style.display = 'block';
                        }}
                    }});
                }});
            }}
        }});
    </script>
    """
    st.components.v1.html(pdf_export_html, height=0, scrolling=False)


# ==========================================
# 5. 登入頁面
# ==========================================
def login_page():
    st.title("⚡ Kadowsella 116 登入")
    st.markdown("### 補習班沒教的數位複習法 | 116 級工程師邏輯戰情室")

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
                        st.success(f"註冊成功！身分：{role}。請登入。")

    with col2:
        st.markdown("---")
        st.write("🚀 **想先看看內容？**")
        if st.button("🚪 以訪客身分試用", use_container_width=True):
            st.session_state.logged_in = True
            st.session_state.username = "訪客"
            st.session_state.role = "guest"
            st.rerun()
        st.link_button("💬 加入 Discord 社群", DISCORD_URL, use_container_width=True)

    # --- 新增：使用者條款與免責聲明 ---
    st.markdown("---")
    with st.expander("⚖️ 使用者條款與免責聲明"):
        st.markdown(f"""
        <div style="font-size: 0.85em; line-height: 1.6; color: gray;">
            <b>【使用者條款與免責聲明】</b><br><br>
            <b>1. 隱私保護</b>：本系統採用 SHA-256 加密技術保護密碼。請勿使用真實姓名或敏感資訊作為帳號。<br>
            <b>2. 內容聲明</b>：所有學科解析與題目均由 AI 輔助生成，僅供 116 級同學複習參考，不保證內容之絕對正確性。<br>
            <b>3. 非營利性質</b>：本專案為個人開發之教育工具，不收取任何費用，亦不提供任何商業服務。<br>
            <b>4. 著作權說明</b>：本站尊重著作權，若內容有侵權疑慮請聯繫管理員處理 email kadowsella@gmail.com。
        </div>
        """, unsafe_allow_html=True)
# ==========================================
# 6. 主程式內容
# ==========================================
def main_app():
    inject_css()

    # --- 1. 資料預加載 ---
    c_df = load_db("Sheet1")      # 知識點資料庫
    q_df = load_db("questions")   # 題庫資料庫
    users_df = load_db("users")   # 使用者資料庫
    l_df = load_db("leaderboard") # 排行榜資料庫

    # --- 2. 獲取當前使用者狀態 ---
    user_row = users_df[users_df['username'] == st.session_state.username] if not users_df.empty else pd.DataFrame()

    # 安全轉換 ai_usage (防止 "無" 或 NaN 導致崩潰)
    try:
        ai_usage = int(float(user_row.iloc[0]['ai_usage'])) if not user_row.empty else 0
    except:
        ai_usage = 0

    # --- 3. 側邊欄導航 (Sidebar) ---
    with st.sidebar:
        role_tag = " <span class='admin-badge'>ADMIN</span>" if st.session_state.role == "admin" else ""
        st.markdown(f"### 👋 你好, {st.session_state.username}{role_tag}", unsafe_allow_html=True)

        if st.session_state.role == "guest":
            st.warning("⚠️ 訪客模式：功能受限")
        else:
            st.markdown(f"<div class='streak-badge'>🔥 116 戰力：Lv.1</div>", unsafe_allow_html=True)

        st.metric("距離 116 學測", f"{CYCLE['days_left']} Days", f"Week {CYCLE['week_num']}")
        st.divider()

        # 選單定義
        menu = ["📅 本週菜單", "🧪 AI 邏輯補給站", "📝 模擬演練", "🏆 戰力排行榜"]
        if st.session_state.role == "admin":
            st.subheader("🛠️ 管理員上帝模式")
            menu.extend(["🔬 預埋考點", "🧪 考題開發", "👤 使用者管理"])

        choice = st.radio("功能導航", menu)

        st.divider()
        st.link_button("💬 Discord 戰情室", DISCORD_URL, use_container_width=True)

        if st.button("🚪 登出系統", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # --- 4. 頁面路由邏輯 ---

    # A. 本週菜單
    if choice == "📅 本週菜單":
        st.title("🚀 116 級本週重點進度")
        st.caption("補習班沒教的數位複習法：用工程師邏輯模組化知識。")
        if not c_df.empty:
            # 顯示最新的 10 筆或當週資料
            for _, r in c_df.tail(10).iterrows():
                show_concept(r)
        else:
            st.info("資料庫建置中，請等待管理員預埋考點。")

    # B. AI 邏輯補給站 (10次限制 + 資料庫驅動)
    elif choice == "🧪 AI 邏輯補給站":
        st.title("🧪 AI 邏輯補給站")
        MAX_USAGE = 10

        if st.session_state.role == "guest":
            st.error("🔒 訪客無法使用 AI 教學，請註冊帳號以解鎖。")
        else:
            if st.session_state.role != "admin":
                st.markdown(f'<div class="quota-box"><h4>🔋 剩餘教學能量：{max(0, MAX_USAGE - ai_usage)} / {MAX_USAGE}</h4></div>', unsafe_allow_html=True)

            if ai_usage >= MAX_USAGE and st.session_state.role != "admin":
                st.error("🚨 能量耗盡！")
                st.warning(f"你已完成 {MAX_USAGE} 次 AI 深度教學。請前往 Discord 找學長補給能量。")
                st.link_button("💬 前往 Discord 找學長", DISCORD_URL)
            else:
                st.info("💡 選擇一個概念，AI 學長將根據資料庫精華為你進行深度導讀。")
                if c_df.empty:
                    st.warning("資料庫目前沒有內容可供教學。")
                else:
                    concept_list = c_df['word'].unique().tolist()
                    selected = st.selectbox("請選擇你想秒懂的概念：", ["--- 請選擇 ---"] + concept_list)

                    if selected != "--- 請選擇 ---":
                        db_row = c_df[c_df['word'] == selected].iloc[0]
                        if st.button("🚀 啟動學長深度教學", use_container_width=True):
                            with st.spinner(f"正在解析「{selected}」的底層邏輯..."):
                                explanation = ai_explain_from_db(db_row)
                                st.markdown("---")
                                st.markdown(explanation) # 支援 LaTeX

                                if st.session_state.role != "admin":
                                    update_user_data(st.session_state.username, "ai_usage", ai_usage + 1)
                                    st.toast("消耗 1 點能量", icon="🔋")

                                # --- 在這裡呼叫 PDF 匯出按鈕 ---
                                if explanation: # 僅在有成功生成解釋時才顯示 PDF 按鈕
                                    pdf_filename = f"{selected}-AI邏輯補給.pdf"
                                    add_pdf_export_button(pdf_filename)
                                # ---------------------------------

    # C. 模擬演練 (支援 LaTeX)
    elif choice == "📝 模擬演練":
        st.title("📝 素養模擬演練")
        if q_df.empty:
            st.info("目前題庫空空如也，請等待管理員出題。")
        else:
            concept_filter = st.selectbox("篩選測驗概念：", ["全部"] + q_df['concept'].unique().tolist())
            filtered_q = q_df if concept_filter == "全部" else q_df[q_df['concept'] == concept_filter]

            for _, row in filtered_q.iterrows():
                with st.container(border=True):
                    st.markdown(f"**【{row['subject']}】{row['concept']}**")
                    st.markdown(row["content"]) # 這裡會自動渲染 $...$ LaTeX

                    with st.expander("🔓 查看答案與防呆解析"):
                        if row['translation'] != "無":
                            st.caption("🌐 中文翻譯")
                            st.markdown(row['translation'])
                        st.success(row['answer_key'])
                    st.divider()

    # D. 戰力排行榜
    elif choice == "🏆 戰力排行榜":
        st.title("🏆 116 戰力排行榜")
        if not l_df.empty:
            st.subheader("🔥 全台 Top 10 巔峰榜")
            top_10 = l_df.sort_values(by="score", ascending=False).head(10)
            st.table(top_10[['username', 'subject', 'score', 'created_at']])

            my_data = l_df[l_df['username'] == st.session_state.username]
            if not my_data.empty:
                st.metric("你的平均戰力值", f"{my_data['score'].mean():.1f} %")
        else:
            st.info("尚無戰績，快去隨機驗收刷一波！")

    # E. 預埋考點 (管理員 - Temp 0.5)
    elif choice == "🔬 預埋考點" and st.session_state.role == "admin":
        st.title("🔬 AI 考點預埋 (上帝模式)")
        c1, c2 = st.columns([3, 1])
        inp = c1.text_input("輸入要拆解的概念", placeholder="例如：光電效應...")
        sub = c2.selectbox("所屬科目", SUBJECTS)

        if st.button("🚀 啟動 AI 深度解碼", use_container_width=True):
            if inp:
                with st.spinner(f"正在拆解「{inp}」..."):
                    sys_prompt = f"你現在是台灣高中名師。請針對「{sub}」的概念「{inp}」進行深度解析。請嚴格輸出 JSON：{{ \"roots\": \"公式\", \"definition\": \"定義\", \"breakdown\": \"拆解\", \"memory_hook\": \"口訣\", \"native_vibe\": \"叮嚀\", \"star\": 5 }}"
                    res = ai_call(sys_prompt, temp=0.5)
                    if res:
                        res.update({"word": inp, "category": sub})
                        st.session_state.temp_concept = res
            else: st.warning("請輸入內容")

        if "temp_concept" in st.session_state:
            show_concept(st.session_state.temp_concept)
            if st.button("💾 確認無誤，存入雲端資料庫", type="primary"):
                if save_to_db(st.session_state.temp_concept, "Sheet1"):
                    st.balloons()
                    del st.session_state.temp_concept
                    st.rerun()

    # F. 考題開發 (管理員)
    elif choice == "🧪 考題開發" and st.session_state.role == "admin":
        st.title("🧪 AI 考題開發")
        if c_df.empty: st.warning("請先預埋考點")
        else:
            target = st.selectbox("選擇要命題的概念：", c_df['word'].unique().tolist())
            if st.button("🪄 生成素養題"):
                db_row = c_df[c_df['word'] == target].iloc[0]
                res = ai_generate_question_from_db(db_row)
                if res: st.session_state.temp_q = res

            if "temp_q" in st.session_state:
                st.markdown(st.session_state.temp_q['content'])
                if st.button("💾 存入題庫"):
                    if save_to_db(st.session_state.temp_q, "questions"):
                        st.success("已存入！")
                        del st.session_state.temp_q
                        st.rerun()

    # G. 使用者管理 (管理員)
    elif choice == "👤 使用者管理" and st.session_state.role == "admin":
        st.title("👤 使用者權限與能量管理")
        for i, row in users_df.iterrows():
            if row['role'] == "admin": continue
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.write(f"**{row['username']}**")
            c2.write(f"已用能量：{row['ai_usage']}")
            if c3.button("能量補滿", key=f"reset_{i}"):
                update_user_data(row['username'], "ai_usage", 0)
                st.rerun()

# ==========================================
# 7. 執行入口
# ==========================================

def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if not st.session_state.logged_in: login_page()
    else: main_app()

if __name__ == "__main__":
    main()
