import random
import streamlit as st
import pandas as pd
import json, re, io, time, hashlib, urllib.parse, ast
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
# 3. AI 引擎 (強化解析版)
# ==========================================
# ==========================================
# 3. AI 引擎 (多 Key 輪替與容錯版)
# ==========================================

def get_api_keys():
    """從 secrets 讀取 Key 列表 (相容單一字串或列表)"""
    # 嘗試讀取複數設定
    keys = st.secrets.get("GEMINI_API_KEYS")
    
    # 如果找不到複數，嘗試讀取單數 (相容舊設定)
    if not keys:
        single_key = st.secrets.get("GEMINI_API_KEY")
        return [single_key] if single_key else []
    
    # 如果使用者在 toml 裡只寫了字串而不是列表，自動轉為列表
    if isinstance(keys, str):
        return [keys]
    
    return keys if keys else []

def robust_json_parse(json_str):
    """
    三階段 JSON 解析器：標準 -> 正則修復 -> Python AST
    """
    if not json_str: return None
    
    # 0. 基礎清理
    json_str = json_str.replace("```json", "").replace("```", "").strip()
    
    # 1. 嘗試直接解析
    try:
        return json.loads(json_str)
    except:
        pass

    # 2. 正則修復 (LaTeX 反斜線與引號)
    fixed_str = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', json_str)
    # 修復未加引號的鍵
    fixed_str = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', fixed_str)
    # 修復單引號的鍵
    fixed_str = re.sub(r"([{,]\s*)'([^']*)'\s*:", r'\1"\2":', fixed_str)

    try:
        return json.loads(fixed_str)
    except:
        pass

    # 3. AST 解析 (處理 Python 風格字典)
    py_str = json_str.replace("true", "True").replace("false", "False").replace("null", "None")
    try:
        return ast.literal_eval(py_str)
    except Exception as e:
        print(f"JSON 解析最終失敗: {e}")
        return None

def ai_generate_question_from_db(db_row):
    """
    (支援多 Key 輪替) 根據資料庫生成題目
    """
    all_keys = get_api_keys()
    if not all_keys:
        st.error("❌ 找不到 API Keys，請檢查 secrets.toml")
        return None

    # 隨機打亂順序，實現負載平衡
    random.shuffle(all_keys)

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

    last_error = None
    # --- 輪替迴圈 ---
    for key in all_keys:
        try:
            genai.configure(api_key=key)
            # 使用 1.5-flash 較穩定，若你有 2.0 權限可改
            model = genai.GenerativeModel('gemini-1.5-flash') 
            
            response = model.generate_content(prompt)
            res_text = response.text
            match = re.search(r'\{.*\}', res_text, re.DOTALL)
            
            if match:
                return robust_json_parse(match.group(0))
            else:
                print(f"Key ...{key[-4:]} 生成格式錯誤，嘗試下一個 Key")
                continue # 格式錯了換下一個試試

        except Exception as e:
            last_error = e
            print(f"⚠️ Key ...{key[-4:]} 失敗: {e} -> 切換下一個")
            continue # 報錯了換下一個
    
    st.error(f"所有 API Key 皆嘗試失敗。最後錯誤: {last_error}")
    return None

def ai_call(system_instruction, user_input="", temp=0.7):
    """
    (支援多 Key 輪替) 通用 AI 呼叫函式
    """
    all_keys = get_api_keys()
    if not all_keys: 
        st.error("❌ 無可用的 API Keys")
        return None

    random.shuffle(all_keys)

    # --- 輪替迴圈 ---
    for key in all_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            response = model.generate_content(
                system_instruction + "\n\n" + user_input,
                generation_config=genai.types.GenerationConfig(temperature=temp)
            )
            res_text = response.text

            # 如果需要 JSON，嘗試解析
            if "JSON" in system_instruction:
                match = re.search(r'\{.*\}', res_text, re.DOTALL)
                if match:
                    return robust_json_parse(match.group(0))
            
            # 如果不是 JSON 需求或解析失敗，直接回傳文字
            return res_text

        except Exception as e:
            print(f"⚠️ Key ...{key[-4:]} 呼叫失敗: {e} -> 自動切換備用線路")
            continue # 嘗試下一個 Key
            
    st.error("🚨 系統忙碌中 (所有 AI 線路皆滿載)，請稍後再試。")
    return None

def ai_decode_concept(input_text, subject):
    sys_prompt = f"""【重要】請嚴格輸出標準 JSON 格式。所有的反斜線 \ 必須寫成 \\ (例如 \\frac, \\sqrt)。你現在是台大醫學系學霸，請針對「{subject}」的概念「{input_text}」進行深度拆解。
    請輸出 JSON：{{ "roots": "核心公式(LaTeX)", "definition": "一句話定義", "breakdown": "重點拆解", "memory_hook": "諧音口訣", "native_vibe": "學長姐叮嚀", "star": 5 }}"""
    res = ai_call(sys_prompt, temp=0.5) 
    if isinstance(res, dict): res.update({"word": input_text, "category": subject})
    return res

def ai_generate_social_post(concept_data):
    sys_prompt = f"""你是一個在 Threads 上發瘋的 116 學測技術宅。你剛用 AI 拆解了「{concept_data['word']}」，覺得 Temp 0 的邏輯美到哭。
    請寫一篇極度厭世、多表情符號、吸引戰友留言『飛翔』的脆文。多用💀、謝了、116。"""
    # 溫度調高一點讓文案更有創意
    return ai_call(sys_prompt, str(concept_data), temp=1.5) 

def ai_explain_from_db(db_row):
    context = f"概念：{db_row['word']} | 定義：{db_row['definition']} | 公式：{db_row['roots']} | 口訣：{db_row['memory_hook']}"
    prompt = f"你是一位台大學霸學長，請根據以下資料進行深度教學，語氣要親切且邏輯清晰，數學公式請使用 LaTeX 格式：\n{context}"
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
def add_pdf_export_button(filename="重點筆記.pdf", title="AI 邏輯補給", content=""):
    """
    生成精美文件版 PDF。
    不截圖螢幕，而是將 content 文字重新排版成 A4 文件格式。
    """
    import json
    
    # 1. 資料清洗與編碼
    # 確保內容是字串，並處理成 JSON 格式以避免引號導致 JS 錯誤
    js_filename = json.dumps(filename, ensure_ascii=False)
    js_title = json.dumps(title, ensure_ascii=False)
    js_content = json.dumps(content, ensure_ascii=False)

    pdf_html = f"""
    <!-- 引入必要的函式庫：Markdown 解析、數學公式渲染、PDF 生成 -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>

    <script>
        function createPdfButton() {{
            const parentDoc = window.parent.document;
            
            // 移除舊按鈕
            const existingBtn = parentDoc.getElementById('export-pdf-btn');
            if (existingBtn) existingBtn.remove();

            // 建立懸浮按鈕
            const btn = parentDoc.createElement("button");
            btn.id = "export-pdf-btn";
            btn.innerHTML = "📄";
            btn.title = "下載精美講義";
            
            // 按鈕樣式 (藍色圓形)
            Object.assign(btn.style, {{
                position: "fixed",
                bottom: "30px",
                right: "30px",
                width: "60px",
                height: "60px",
                borderRadius: "50%",
                backgroundColor: "#6366f1",
                color: "white",
                border: "none",
                fontSize: "24px",
                cursor: "pointer",
                boxShadow: "0 4px 15px rgba(99, 102, 241, 0.4)",
                zIndex: "999999",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "all 0.3s ease"
            }});

            btn.onmouseover = function() {{ this.style.backgroundColor = "#4f46e5"; }};
            btn.onmouseout = function() {{ this.style.backgroundColor = "#6366f1"; }};

            btn.onclick = function() {{
                btn.innerHTML = "⏳";
                btn.disabled = true;

                // 1. 準備數據
                const docTitle = {js_title};
                const rawContent = {js_content};

                // 2. 建立一個隱藏的「文件容器」
                // 這就是我們要印出來的樣子，完全由我們控制 CSS，與網頁原本長相無關
                const container = document.createElement('div');
                container.id = 'pdf-hidden-container';
                
                // 設定文件樣式 (仿 Word/講義排版)
                container.style.cssText = `
                    position: fixed; 
                    top: -9999px; 
                    left: -9999px; 
                    width: 210mm; /* A4 寬度 */
                    min-height: 297mm;
                    background: white; 
                    color: black;
                    padding: 20mm;
                    font-family: "Microsoft JhengHei", "Segoe UI", sans-serif;
                    line-height: 1.6;
                `;

                // 3. 組合 HTML 內容
                // 將 Markdown 轉為 HTML
                const htmlContent = marked.parse(rawContent);

                container.innerHTML = `
                    <div style="border-bottom: 3px solid #6366f1; padding-bottom: 10px; margin-bottom: 20px;">
                        <h1 style="color: #1e3a8a; margin: 0; font-size: 24px;">⚡ 116 戰情室重點筆記</h1>
                        <p style="color: #6b7280; margin: 5px 0 0 0; font-size: 14px;">主題：${{docTitle}}</p>
                    </div>
                    <div class="content-body" style="font-size: 14px;">
                        ${{htmlContent}}
                    </div>
                    <div style="margin-top: 30px; text-align: center; color: #9ca3af; font-size: 10px; border-top: 1px solid #e5e7eb; padding-top: 10px;">
                        此講義由 Kadowsella 116 AI 戰情室生成，僅供學習使用。
                    </div>
                `;
                
                // 額外的 CSS 美化 Markdown 轉出來的內容
                const style = document.createElement('style');
                style.innerHTML = `
                    #pdf-hidden-container h1, #pdf-hidden-container h2, #pdf-hidden-container h3 {{ color: #1e3a8a; margin-top: 1.5em; }}
                    #pdf-hidden-container strong {{ color: #d946ef; }} /* 重點強調色 */
                    #pdf-hidden-container blockquote {{ 
                        background: #f3f4f6; 
                        border-left: 4px solid #6366f1; 
                        padding: 10px; 
                        margin: 10px 0; 
                        color: #4b5563;
                    }}
                    #pdf-hidden-container code {{ 
                        background: #f3f4f6; 
                        padding: 2px 5px; 
                        border-radius: 4px; 
                        color: #dc2626;
                        font-family: monospace;
                    }}
                `;
                container.appendChild(style);
                document.body.appendChild(container);

                // 4. 渲染數學公式 (KaTeX)
                renderMathInElement(container, {{
                    delimiters: [
                        {{left: "$$", right: "$$", display: true}},
                        {{left: "$", right: "$", display: false}},
                        {{left: "\\\\(", right: "\\\\)", display: false}},
                        {{left: "\\\\[", right: "\\\\]", display: true}}
                    ],
                    throwOnError: false
                }});

                // 5. 生成 PDF
                const opt = {{
                    margin: 0, // 我們自己在 container 設定了 padding，這裡設 0
                    filename: {js_filename},
                    image: {{ type: 'jpeg', quality: 0.98 }},
                    html2canvas: {{ scale: 2, useCORS: true, logging: false }},
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                }};

                html2pdf().set(opt).from(container).save().then(() => {{
                    // 清理
                    document.body.removeChild(container);
                    btn.innerHTML = "📄";
                    btn.disabled = false;
                }}).catch(err => {{
                    console.error(err);
                    if(document.getElementById('pdf-hidden-container')) {{
                        document.body.removeChild(container);
                    }}
                    btn.innerHTML = "❌";
                    btn.disabled = false;
                }});
            }};

            parentDoc.body.appendChild(btn);
        }}

        setTimeout(createPdfButton, 1000);
    </script>
    """
    st.components.v1.html(pdf_html, height=0)
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

                                # --- PDF 匯出按鈕 ---
                                if explanation:
                                    # 定義檔名
                                    pdf_filename = f"{selected}_重點筆記.pdf"
                                    
                                    # 呼叫新函式，傳入：檔名、標題、以及最重要的「內容字串」
                                    # 注意：explanation 是 AI 產生出來的那一大段文字
                                    add_pdf_export_button(
                                        filename=pdf_filename, 
                                        title=selected, 
                                        content=explanation
                                        )

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
                    st.markdown(row["content"])

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
                    sys_prompt = f"你現在是台灣高中名師。請針對「{sub}」的概念「{inp}」進行深度解析。請嚴格輸出 JSON：{{ \"roots\": \"核心公式(LaTeX)\", \"definition\": \"一句話定義\", \"breakdown\": \"重點拆解\", \"memory_hook\": \"諧音口訣\", \"native_vibe\": \"叮嚀\", \"star\": 5 }}"
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
