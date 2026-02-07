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
        
        if sheet_name == "users":
            # 強制檢查必要欄位
            expected_cols = ['username', 'password', 'role', 'membership', 'ai_usage', 'created_at']
            for col in expected_cols:
                if col not in df.columns:
                    # 如果沒這欄，自動補上預設值
                    df[col] = "free" if col == "membership" else (0 if col == "ai_usage" else "無")
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

def ai_generate_question_from_db(db_row, tier="free"):
    """
    (支援多 Key 輪替) 根據資料庫生成題目
    """
    all_keys = get_api_keys()
    if not all_keys: return None

    # 分流與模型選擇
    if tier == "self":
        target_keys = [st.secrets.get("GEMINI_SELF_KEY")]
        model_name = "gemini-2.5-pro"
    elif tier == "paid":
        target_keys = st.secrets.get("GEMINI_PAID_KEYS", [])
        model_name = "gemini-2.5-pro"
    else:
        target_keys = st.secrets.get("GEMINI_FREE_KEYS", [])
        model_name = "gemini-2.5-flash"

    random.shuffle(target_keys)

    prompt = f"""
    你現在是台灣大考中心命題委員。請根據以下資料出一題「108課綱素養導向」的選擇題。
    【參考資料】：概念：{db_row['word']} | 科目：{db_row['category']} | 定義：{db_row['definition']}
    【重要規範】：
    1. 所有的數學符號、座標、公式、根號，必須使用 LaTeX 格式並用單個錢字號包裹。
    2. 題目必須包含「情境描述」與「問題內容」。
    請嚴格輸出 JSON 格式。
    """

    for key in target_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if match:
                return robust_json_parse(match.group(0))
        except:
            continue
    return None
def ai_call(system_instruction, user_input="", temp=0.7, tier="free"):
    """
    三線分流 AI 呼叫引擎
    tier: "free" (預設), "paid" (PRO會員), "self" (管理員)
    """
    # 1. 根據等級選擇鑰匙池與模型
    if tier == "self":
        target_keys = [st.secrets.get("GEMINI_SELF_KEY")]
        model_name = "gemini-3.0-pro" # 自用給最好的
    elif tier == "paid":
        target_keys = st.secrets.get("GEMINI_PAID_KEYS", [])
        model_name = "gemini-2.5-pro" # 付費版用最強邏輯
    else:
        target_keys = st.secrets.get("GEMINI_FREE_KEYS", [])
        model_name = "gemini-2.5-flash" # 免費版求快求穩

    if not target_keys or not target_keys[0]:
        return "❌ 系統錯誤：找不到對應等級的 API Key"

    # 2. 洗牌 (除了自用只有一把不用洗)
    if len(target_keys) > 1:
        random.shuffle(target_keys)

    # 3. 輪替重試邏輯
    for key in target_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name)
            
            response = model.generate_content(
                system_instruction + "\n\n" + user_input,
                generation_config=genai.types.GenerationConfig(temperature=temp)
            )
            res_text = response.text

            # JSON 解析處理
            if "JSON" in system_instruction:
                match = re.search(r'\{.*\}', res_text, re.DOTALL)
                if match:
                    return robust_json_parse(match.group(0))
            
            return res_text

        except Exception as e:
            # 如果是自用 Key 報錯，直接噴
            if tier == "self": return f"🚨 自用 Key 報錯: {e}"
            # 其他則印出 log 並試下一把
            print(f"⚠️ {tier.upper()} 線路 Key 異常: {e} -> 切換中")
            continue

    return "🚨 所有對應線路皆忙碌中，請稍後再試。"
    
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
    return ai_call(sys_prompt, str(concept_data), temp=2.5) 

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
def show_pro_paper_with_download(title, content):
    """
    在網頁上直接顯示精美講義，並在下方附帶下載按鈕。
    解決按鈕消失、LaTeX 不美觀、排版混亂三大問題。
    """
    js_title = json.dumps(title, ensure_ascii=False)
    js_content = json.dumps(content, ensure_ascii=False)
    
    # 產生唯一的 ID 避免衝突
    div_id = f"paper_{int(time.time())}"

    html_code = f"""
    <div id="{div_id}_wrapper" style="background: var(--secondary-background-color); padding: 20px; border-radius: 15px; border: 1px solid var(--border-color); margin: 20px 0;">
        <!-- 內容顯示區 -->
        <div id="{div_id}_content" style="color: inherit; font-family: inherit; line-height: 1.6;">
            載入中...
        </div>
        
        <hr style="border: 0; border-top: 1px solid var(--border-color); margin: 20px 0;">
        
        <!-- 下載按鈕 (直接長在內容下方) -->
        <button id="{div_id}_btn" style="
            width: 100%; padding: 12px; background-color: #6366f1; color: white; 
            border: none; border-radius: 10px; cursor: pointer; font-size: 16px; font-weight: bold;
        ">📥 下載此篇精美講義 (PDF)</button>
    </div>

    <!-- 載入必要函式庫 -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>

    <script>
        (function() {{
            const rawContent = {js_content};
            const title = {js_title};
            const displayDiv = document.getElementById("{div_id}_content");
            const btn = document.getElementById("{div_id}_btn");

            // 1. 渲染畫面上的 Markdown 與 LaTeX
            displayDiv.innerHTML = marked.parse(rawContent);
            renderMathInElement(displayDiv, {{
                delimiters: [
                    {{left: "$$", right: "$$", display: true}},
                    {{left: "$", right: "$", display: false}}
                ]
            }});

            // 2. 下載邏輯
            btn.onclick = function() {{
                btn.innerHTML = "⏳ 正在排版並生成 PDF...";
                btn.disabled = true;

                // 建立專屬排版容器
                const container = document.createElement('div');
                container.style.cssText = "width:210mm; background:white; color:black; padding:20mm; font-family:sans-serif;";
                container.innerHTML = `
                    <div style="border-left: 10px solid #6366f1; padding-left: 20px; margin-bottom: 30px;">
                        <h1 style="font-size: 28px; color: #1e3a8a; margin: 0;">⚡ 116 級數位戰情室</h1>
                        <p style="font-size: 16px; color: #6b7280; margin: 5px 0;">學習重點：${{title}}</p>
                    </div>
                    <div style="font-size: 14px; line-height: 1.8;">${{marked.parse(rawContent)}}</div>
                `;
                document.body.appendChild(container);

                // 再次渲染 PDF 內的數學公式
                renderMathInElement(container, {{ delimiters: [{{left: "$$", right: "$$", display: true}}, {{left: "$", right: "$", display: false}}] }});

                const opt = {{
                    margin: 10, filename: title + "_116重點.pdf",
                    image: {{ type: 'jpeg', quality: 1 }},
                    html2canvas: {{ scale: 2, useCORS: true }},
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                }};

                html2pdf().set(opt).from(container).save().then(() => {{
                    document.body.removeChild(container);
                    btn.innerHTML = "📥 下載成功！";
                    btn.disabled = false;
                    setTimeout(() => btn.innerHTML = "📥 下載此篇精美講義 (PDF)", 3000);
                }});
            }};
        }})();
    </script>
    """
    # 設定高度讓它能完整顯示內容
    st.components.v1.html(html_code, height=600, scrolling=True)
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
                    # 判斷身分
                    is_admin = admin_code == st.secrets.get("ADMIN_PASSWORD")
                    role = "admin" if is_admin else "student"
                    # 管理員註冊預設就是 pro 等級，一般人是 free
                    membership = "pro" if is_admin else "free"
                    
                    user_data = {
                        "username": new_u, 
                        "password": hash_password(new_p), 
                        "role": role, 
                        "membership": membership, # 👈 確保這行有寫入
                        "ai_usage": 0, 
                        "can_chat": "FALSE"
                    }
                    
                    if save_to_db(user_data, "users"):
                        st.success(f"註冊成功！身分：{role}。請切換至登入分頁。")

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
    
    # --- 2. 獲取當前使用者詳細狀態 ---
    user_row = users_df[users_df['username'] == st.session_state.username] if not users_df.empty else pd.DataFrame()
    
    # 權限變數定義
    is_admin = st.session_state.role == "admin"
    user_membership = user_row.iloc[0].get('membership', 'free') if not user_row.empty else 'free'
    is_pro = user_membership == "pro"
    
    # 安全獲取 AI 使用量
    try:
        ai_usage = int(float(user_row.iloc[0]['ai_usage'])) if not user_row.empty else 0
    except:
        ai_usage = 0

    # --- 3. 在線狀態同步 (Heartbeat) ---
    def sync_online_status(username):
        if "last_sync_time" not in st.session_state:
            st.session_state.last_sync_time = 0
        
        # 每 3 分鐘更新一次資料庫，避免過於頻繁
        if time.time() - st.session_state.last_sync_time > 180:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            update_user_data(username, "last_seen", now_str)
            update_user_data(username, "is_online", "TRUE")
            st.session_state.last_sync_time = time.time()

    sync_online_status(st.session_state.username)

    # --- 4. 側邊欄導航 (Sidebar) ---
    with st.sidebar:
        # 身分標籤顯示
        if is_admin:
            role_label = "（ADMIN）"
        elif is_pro:
            role_label = f"（PRO）：{st.session_state.username}"
        else:
            role_label = "（學生）"
            
        st.markdown(f"### 👋 你好, {st.session_state.username}")
        st.caption(role_label)

        # 功能選單
        menu = ["📅 本週菜單", "🧪 AI 邏輯補給站", "📝 模擬演練", "🏆 戰力排行榜"]
        
        # PRO 以上解鎖開發工具
        if is_admin or is_pro:
            st.divider()
            st.subheader("🛠️ 開發者/PRO 工具")
            menu.append("🔬 預埋考點")
            menu.append("🧪 考題開發")
            
        # 僅 Admin 可見
        if is_admin:
            menu.append("👤 使用者管理")

        choice = st.radio("功能導航", menu)

        st.divider()
        st.metric("距離 116 學測", f"{CYCLE['days_left']} Days", f"Week {CYCLE['week_num']}")
        st.link_button("💬 Discord 戰情室", DISCORD_URL, use_container_width=True)

        if st.button("🚪 登出系統", use_container_width=True):
            update_user_data(st.session_state.username, "is_online", "FALSE")
            st.session_state.logged_in = False
            st.rerun()

    # --- 5. 功能路由 ---

    # A. 本週菜單
    if choice == "📅 本週菜單":
        st.title("🚀 116 級本週重點進度")
        if not c_df.empty:
            for _, r in c_df.tail(10).iterrows():
                show_concept(r)
        else:
            st.info("資料庫建置中...")

    # B. AI 邏輯補給站 (生內容 + PDF)
    elif choice == "🧪 AI 邏輯補給站":
        st.title("🧪 AI 邏輯補給站")
        
        if not is_admin:
            st.markdown(f'<div class="quota-box"><h4>🔋 剩餘教學能量：{max(0, 10 - ai_usage)} / 10</h4></div>', unsafe_allow_html=True)

        if ai_usage >= 10 and not is_admin:
            st.error("🚨 能量耗盡！請聯繫管理員升級 PRO。")
        else:
            concept_list = c_df['word'].unique().tolist() if not c_df.empty else []
            selected = st.selectbox("選擇你想秒懂的概念：", ["--- 請選擇 ---"] + concept_list)
            
            # 1. 點擊生成按鈕
            if selected != "--- 請選擇 ---":
                db_row = c_df[c_df['word'] == selected].iloc[0]
                if st.button("🚀 啟動學長深度教學", use_container_width=True):
                    with st.spinner(f"正在解析「{selected}」的底層邏輯..."):
                        # 呼叫 AI
                        explanation = ai_explain_from_db(db_row)
                        # 將結果存入 session_state 確保重新整理後還在
                        st.session_state.current_explanation = explanation
                        st.session_state.current_selected = selected
                        
                        if not is_admin:
                            update_user_data(st.session_state.username, "ai_usage", ai_usage + 1)
                            st.toast("消耗 1 點能量", icon="🔋")

            # 2. 只要 session_state 裡有內容，就顯示出來
            if "current_explanation" in st.session_state and st.session_state.current_selected == selected:
            st.markdown("---")
            # 這裡我們不再用 st.markdown，改用我們的精美組件
            show_pro_paper_with_download(
                title=st.session_state.current_selected,
                content=st.session_state.current_explanation
            )
            # 1. 產生 PDF 資料 (放在記憶體內)
            try:
                pdf_data = generate_native_pdf(
                    title=st.session_state.current_selected,
                    content=st.session_state.current_explanation
                )
                
                # 2. 顯示原生下載按鈕 (絕對不會不見)
                st.download_button(
                    label="📥 下載專屬複習講義 (PDF)",
                    data=pdf_data,
                    file_name=f"{st.session_state.current_selected}_116重點.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"PDF 產生失敗，可能是缺字型檔：{e}")

    # E. 預埋考點 (PRO/ADMIN 貢獻模式)
    elif choice == "🔬 預埋考點" and (is_admin or is_pro):
        st.title("🔬 AI 考點預埋 (上帝/PRO 模式)")
        c1, c2 = st.columns([3, 1])
        inp = c1.text_input("輸入要拆解的概念", placeholder="例如：向量外積...")
        sub = c2.selectbox("所屬科目", SUBJECTS)

        if st.button("🚀 啟動 AI 深度解碼", use_container_width=True):
            if inp:
                with st.spinner(f"正在拆解「{inp}」..."):
                    # 分流：Admin 用 self, Pro 用 paid
                    tier_type = "self" if is_admin else "paid"
                    sys_prompt = f"你現在是台灣高中名師。請針對「{sub}」的概念「{inp}」進行深度解析。請嚴格輸出 JSON：{{ \"roots\": \"核心公式(LaTeX)\", \"definition\": \"一句話定義\", \"breakdown\": \"重點拆解\", \"memory_hook\": \"諧音口訣\", \"native_vibe\": \"叮嚀\", \"star\": 5 }}"
                    res = ai_call(sys_prompt, temp=0.5, tier=tier_type)
                    if res:
                        res.update({"word": inp, "category": sub})
                        st.session_state.temp_concept = res
            else: st.warning("請輸入內容")

        if "temp_concept" in st.session_state:
            show_concept(st.session_state.temp_concept)
            if st.button("💾 確認無誤，存入大資料庫", type="primary"):
                # 製作貢獻者標籤
                tag = "（ADMIN）" if is_admin else f"（PRO）：{st.session_state.username}"
                final_data = st.session_state.temp_concept.copy()
                final_data['contributor'] = tag
                
                if save_to_db(final_data, "Sheet1"):
                    st.balloons()
                    st.success(f"存檔成功！貢獻標記：{tag}")
                    del st.session_state.temp_concept
                    st.rerun()

    # F. 考題開發 (PRO/ADMIN 模式)
    elif choice == "🧪 考題開發" and (is_admin or is_pro):
        st.title("🧪 AI 考題開發")
        if c_df.empty: st.warning("請先預埋考點")
        else:
            target = st.selectbox("選擇要命題的概念：", c_df['word'].unique().tolist())
            if st.button("🪄 生成素養題"):
                db_row = c_df[c_df['word'] == target].iloc[0]
                # 修正：呼叫函式並帶入 tier
                tier_type = "self" if is_admin else "paid"
                res = ai_generate_question_from_db(db_row, tier=tier_type)
                if res: st.session_state.temp_q = res

            if "temp_q" in st.session_state:
                st.markdown(st.session_state.temp_q['content'])
                if st.button("💾 存入題庫", type="primary"):
                    tag = "（ADMIN）" if is_admin else f"（PRO）：{st.session_state.username}"
                    final_q = st.session_state.temp_q.copy()
                    final_q['contributor'] = tag
                    if save_to_db(final_q, "questions"):
                        st.success(f"已存入題庫！來源：{tag}")
                        del st.session_state.temp_q
                        st.rerun()

    # G. 使用者管理 (僅限 Admin)
    elif choice == "👤 使用者管理" and is_admin:
        st.title("👤 戰情室成員管理")
        # 即時重讀資料
        users_df = load_db("users")
        
        for i, row in users_df.iterrows():
            if row['role'] == "admin": continue
            
            # 在線狀態判斷
            is_online = row.get('is_online', 'FALSE') == "TRUE"
            last_seen = row.get('last_seen', '無')
            status_dot = "🟢" if is_online else "🔴"
            
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            c1.write(f"**{row['username']}** {status_dot}")
            c2.caption(f"Last: {last_seen}")
            
            # 升降級按鈕
            if row.get('membership') == 'free':
                if c3.button("升級 PRO", key=f"up_{i}"):
                    update_user_data(row['username'], "membership", "pro")
                    st.rerun()
            else:
                if c3.button("降級 FREE", key=f"down_{i}"):
                    update_user_data(row['username'], "membership", "free")
                    st.rerun()
            
            if c4.button("⚡ 補能", key=f"refill_{i}"):
                update_user_data(row['username'], "ai_usage", 0)
                st.rerun()

# F. 考題開發 (管理員 & PRO 會員解鎖)
    elif choice == "🧪 考題開發":
        # 1. 權限前置檢查，避免 iloc[0] 報錯
        is_admin = st.session_state.get('role') == "admin"
        is_pro = not user_row.empty and user_row.iloc[0].get('membership') == 'pro'
    
        if is_admin or is_pro:
            st.title("🧪 AI 考題開發")
            
            # 2. 檢查是否有預埋的概念資料 (c_df)
            if c_df.empty:
                st.warning("請先去「🔬 預埋考點」新增概念，才能根據概念出題。")
            else:
                # 取得不重複的概念清單
                concept_list = c_df['word'].unique().tolist()
                target_concept = st.selectbox("選擇要命題的概念：", concept_list)
                
                if st.button("🪄 根據此概念生成素養題", use_container_width=True):
                    # 取得選定概念的完整資料列
                    db_row = c_df[c_df['word'] == target_concept].iloc[0]
                    
                    with st.spinner(f"命題委員正在針對「{target_concept}」構思情境..."):
                        # 3. 確保 API Key 邏輯與上一段一致
                        # 假設你的 ai_generate_question_from_db 內部會用到 API
                        # 你可能需要傳入選定的 API Key
                        target_key_name = "GEMINI_PAID_KEYS" if is_admin else "GEMINI_SELF_KEY"
                        selected_api_key = st.secrets.get(target_key_name)
                        
                        if not selected_api_key:
                            st.error(f"找不到 API Key: {target_key_name}，請檢查設定。")
                            st.stop()
                        
                        # 執行生成 (建議將 api_key 作為參數傳入，除非你的函數內部已處理)
                        new_q = ai_generate_question_from_db(db_row, api_key=selected_api_key)
                        
                        if new_q:
                            st.session_state.temp_q = new_q
                            st.success("題目生成成功！請檢查下方預覽。")
                            # 建議在這裡加一個展示區域
                            with st.expander("📝 題目預覽", expanded=True):
                                st.write(new_q)
                        else:
                            st.error("AI 命題失敗，請稍後再試。")
        else:
            st.error("🚫 此功能僅限 PRO 會員或管理員使用。")
            st.info("若您已是 PRO 會員卻看到此訊息，請確認您的帳號狀態。")
    
            if "temp_q" in st.session_state:
                st.markdown(st.session_state.temp_q['content'])
                if st.button("💾 存入題庫"):
                    
                    # --- 關鍵修改 2: 準備儲存資料 ---
                    data_to_save = st.session_state.temp_q.copy()
                    data_to_save['contributor'] = st.session_state.username # 填入使用者名稱
                    
                    if save_to_db(data_to_save, "questions"):
                        st.success("已存入！")
                        del st.session_state.temp_q
                        st.rerun()
                        
    # G. 使用者管理 (管理員)
    elif choice == "👤 使用者管理" and st.session_state.role == "admin":
        st.title("👤 使用者管理")
        for i, row in users_df.iterrows():
            if row['role'] == "admin": continue
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            c1.write(f"**{row['username']}**")
            c2.write(f"等級：{row['membership']}")
            
            # 升級 PRO 按鈕
            if row['membership'] == 'free':
                if c3.button("升級 PRO", key=f"up_{i}"):
                    update_user_data(row['username'], "membership", "pro")
                    st.rerun()
            else:
                if c3.button("降級 FREE", key=f"down_{i}"):
                    update_user_data(row['username'], "membership", "free")
                    st.rerun()
    if "current_explanation" in st.session_state:
        add_pdf_export_button(
            filename=f"{st.session_state.current_selected}_筆記.pdf", 
            title=st.session_state.current_selected, 
            content=st.session_state.current_explanation
        )
# ==========================================
# 7. 執行入口
# ==========================================

def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if not st.session_state.logged_in: login_page()
    else: main_app()

if __name__ == "__main__":
    main()
