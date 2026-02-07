import random
import streamlit as st
import pandas as pd
import json, re, io, time, hashlib, urllib.parse, ast
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
# 2. 工具函式 (Hash, DB, JSON)
# ==========================================
def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()

def load_db(sheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0)
        if sheet_name == "users":
            for col in ['username', 'password', 'role', 'membership', 'ai_usage', 'is_online', 'last_seen']:
                if col not in df.columns: df[col] = "free" if col=="membership" else "無"
        return df.fillna("無")
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
    except: pass

def robust_json_parse(json_str):
    if not json_str: return None
    json_str = json_str.replace("```json", "").replace("```", "").strip()
    try: return json.loads(json_str)
    except:
        fixed = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', json_str)
        try: return json.loads(fixed)
        except:
            try: return ast.literal_eval(json_str.replace("true", "True").replace("false", "False").replace("null", "None"))
            except: return None

# ==========================================
# 3. AI 核心 (分流與輪替)
# ==========================================
def get_api_keys():
    keys = st.secrets.get("GEMINI_FREE_KEYS")
    return keys if isinstance(keys, list) else [st.secrets.get("GEMINI_API_KEY")]

def ai_call(system_instruction, user_input="", temp=0.7, tier="free"):
    if tier == "self":
        target_keys, model_name = [st.secrets.get("GEMINI_SELF_KEY")], "gemini-2.5-pro"
    elif tier == "paid":
        target_keys, model_name = st.secrets.get("GEMINI_PAID_KEYS", []), "gemini-2.5-pro"
    else:
        target_keys, model_name = get_api_keys(), "gemini-2.5-flash"

    if not target_keys or not target_keys[0]: return "❌ API Key 未設定"
    random.shuffle(target_keys)

    for key in target_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name)
            res = model.generate_content(system_instruction + "\n\n" + user_input, generation_config=genai.types.GenerationConfig(temperature=temp))
            if "JSON" in system_instruction:
                match = re.search(r'\{.*\}', res.text, re.DOTALL)
                return robust_json_parse(match.group(0)) if match else None
            return res.text
        except: continue
    return "🚨 所有線路忙碌中"

def ai_generate_question_from_db(db_row, tier="free"):
    """
    (支援多 Key 輪替) 你現在是台灣大考中心命題委員。
    """
    prompt = f"""
    你現在是台灣大考中心命題委員。請根據以下資料出一題「108課綱素養導向」的選擇題。
    
    【參考資料】：
    概念：{db_row['word']}
    科目：{db_row['category']}
    定義：{db_row['definition']}
    核心邏輯：{db_row.get('roots', '無')}
    
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
    return ai_call("你必須嚴格輸出標準 JSON 格式。", prompt, tier=tier)

def ai_decode_concept(input_text, subject):
    """
    台大醫學系學霸深度拆解邏輯
    """
    sys_prompt = f"""
    【重要】請嚴格輸出標準 JSON 格式。所有的反斜線 \ 必須寫成 \\ (例如 \\frac, \\sqrt)。
    你現在是台大醫學系學霸，請針對「{subject}」的概念「{input_text}」進行深度拆解。
    請輸出 JSON：
    {{ 
        "roots": "核心公式(LaTeX)或字源邏輯", 
        "definition": "一句話秒懂定義", 
        "breakdown": "重點深度拆解(使用\\n換行)", 
        "memory_hook": "諧音口訣或記憶點", 
        "native_vibe": "學長姐血淚叮嚀/雷區警告", 
        "star": 5 
    }}
    """
    return ai_call(sys_prompt, temp=0.5, tier="paid") # 邏輯拆解用付費線路

def ai_explain_from_db(db_row):
    """
    親切且邏輯清晰的台大學霸深度導讀
    """
    context = f"概念：{db_row['word']} | 定義：{db_row['definition']} | 公式：{db_row.get('roots', '無')} | 口訣：{db_row.get('memory_hook', '無')}"
    prompt = f"""
    你是一位台大學霸學長，請根據以下資料進行深度教學，語氣要親切、幽默且邏輯清晰。
    
    資料：{context}
    
    要求：
    1. 所有的數學公式、符號、根號、座標，請務必使用 LaTeX 格式（單個 $ 包裹）。
    2. 內容要包含：原理解析、生活實例、以及「為什麼考這個」。
    3. 最後要有一個充滿能量的結語。
    """
    return ai_call(prompt, temp=0.7, tier="free")

def ai_generate_social_post(concept_data):
    """
    Threads 發瘋的 116 技術宅 (脆文)
    """
    sys_prompt = f"""
    你是一個在 Threads (脆) 上發瘋的 116 學測技術宅。
    你剛用 AI 拆解了「{concept_data['word']}」，覺得 Temp 0 的邏輯美到哭。
    請寫一篇極度厭世、多表情符號、吸引戰友留言『飛翔』的脆文。
    多用💀、謝了、116、這邏輯絕了。
    """
    return ai_call(sys_prompt, str(concept_data), temp=1.5, tier="free")
# ==========================================
# 4. UI 與 PDF 組件
# ==========================================
def inject_css():
    st.markdown("""<style>
        .card { border-radius: 15px; padding: 20px; background: var(--secondary-background-color); border-left: 8px solid #6366f1; margin-bottom: 20px; }
        .tag { background: #6366f1; color: white; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; }
        .quota-box { padding: 15px; border-radius: 10px; border: 1px solid #6366f1; text-align: center; }
    </style>""", unsafe_allow_html=True)

def show_concept(row):
    contrib = row.get('contributor', '')
    st.markdown(f"""<div class="card"><span class="tag">{row['category']}</span> <span style="float:right;color:gray;">{contrib}</span>
    <h2>{row['word']}</h2><p><b>💡 秒懂：</b>{row['definition']}</p></div>""", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"🧬 **核心邏輯**\n\n{row['roots']}")
        st.success(f"🧠 **記憶點**\n\n{row['memory_hook']}")
    with c2:
        st.warning(f"🚩 **雷區**\n\n{row['native_vibe']}")
        with st.expander("🔍 詳細拆解"):
            st.write(row['breakdown'])
def show_pro_paper_with_download(title, content):
    js_title, js_content = json.dumps(title, ensure_ascii=False), json.dumps(content, ensure_ascii=False)
    div_id = f"paper_{int(time.time())}"
    html_code = f"""
    <div id="{div_id}_wrapper" style="background:#1e1e1e; padding:25px; border-radius:15px; border:1px solid #333; color:white; margin:20px 0;">
        <div id="{div_id}_content" style="margin-bottom:20px; line-height:1.6;">載入內容中...</div>
        <hr style="border:0; border-top:1px solid #444; margin:20px 0;">
        <button id="{div_id}_btn" style="width:100%; padding:15px; background:linear-gradient(90deg, #6366f1, #a855f7); color:white; border:none; border-radius:10px; cursor:pointer; font-weight:bold; font-size:16px;">📥 下載精美複習講義 (PDF)</button>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script>
        (function() {{
            const content = {js_content}; const title = {js_title};
            const display = document.getElementById("{div_id}_content");
            display.innerHTML = marked.parse(content);
            renderMathInElement(display, {{ delimiters: [{{left: "$$", right: "$$", display: true}}, {{left: "$", right: "$", display: false}}] }});
            
            document.getElementById("{div_id}_btn").onclick = function() {{
                this.innerHTML = "⏳ 正在排版...";
                const container = document.createElement('div');
                container.style.cssText = "width:210mm; background:white; color:black; padding:25mm; font-family:sans-serif;";
                container.innerHTML = `
                    <div style="border-left:8px solid #6366f1; padding-left:20px; margin-bottom:30px;">
                        <h1 style="color:#1e3a8a; margin:0; font-size:28px;">⚡ 116 級數位戰情室</h1>
                        <p style="color:#666; margin:5px 0; font-size:16px;">重點主題：${{title}} | 專屬複習講義</p>
                    </div>
                    <div style="line-height:1.8; font-size:14px;">${{marked.parse(content)}}</div>
                    <div style="margin-top:50px; border-top:1px dashed #ccc; padding-top:10px; text-align:center; color:#999; font-size:10px;">
                        Kadowsella 116 AI 模組化知識庫 | 此份文件僅供內部學習使用
                    </div>
                `;
                document.body.appendChild(container);
                renderMathInElement(container, {{ delimiters: [{{left: "$$", right: "$$", display: true}}, {{left: "$", right: "$", display: false}}] }});
                html2pdf().set({{ margin:0, filename: title+"_116講義.pdf", image:{{type:'jpeg', quality:1}}, html2canvas:{{scale:2, useCORS:true}}, jsPDF:{{unit:'mm', format:'a4', orientation:'portrait'}} }})
                .from(container).save().then(() => {{ document.body.removeChild(container); this.innerHTML = "📥 下載成功！"; }});
            }};
        }})();
    </script>"""
    st.components.v1.html(html_code, height=600, scrolling=True)
# ==========================================
# 5. 頁面邏輯 (登入/主程式)
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
                    user = users[(users['username'] == u) & (users['password'] == hash_password(p))]
                    if not user.empty:
                        st.session_state.logged_in, st.session_state.username, st.session_state.role = True, u, user.iloc[0]['role']
                        update_user_data(u, "is_online", "TRUE")
                        st.rerun()
                    else: st.error("❌ 帳號或密碼錯誤")
        
        with tab2:
            with st.form("reg"):
                nu, np, code = st.text_input("設定帳號"), st.text_input("設定密碼", type="password"), st.text_input("管理員邀請碼 (學生免填)", type="password")
                if st.form_submit_button("完成註冊"):
                    is_admin = (code == st.secrets.get("ADMIN_PASSWORD"))
                    user_data = {
                        "username": nu, "password": hash_password(np), 
                        "role": "admin" if is_admin else "student",
                        "membership": "pro" if is_admin else "free", "ai_usage": 0
                    }
                    if save_to_db(user_data, "users"):
                        st.success("註冊成功！請切換至登入分頁。")

    with col2:
        st.markdown("---")
        st.write("🚀 **想先看看內容？**")
        if st.button("🚪 以訪客身分試用", use_container_width=True):
            st.session_state.logged_in, st.session_state.username, st.session_state.role = True, "訪客", "guest"
            st.rerun()
        st.link_button("💬 加入 Discord 社群", DISCORD_URL, use_container_width=True)

    st.markdown("---")
    with st.expander("⚖️ 使用者條款與免責聲明"):
        st.markdown("""
        <div style="font-size: 0.85em; line-height: 1.6; color: gray;">
            <b>【使用者條款與免責聲明】</b><br><br>
            <b>1. 隱私保護</b>：本系統採用 SHA-256 加密技術保護密碼。請勿使用真實姓名作為帳號。<br>
            <b>2. 內容聲明</b>：所有學科解析與題目均由 AI 輔助生成，僅供複習參考，不保證內容絕對正確。<br>
            <b>3. 非營利性質</b>：本專案為個人開發之教育工具，不收取費用，亦不提供商業服務。<br>
            <b>4. 著作權說明</b>：本站尊重著作權，若有侵權疑慮請聯繫 kadowsella@gmail.com。
        </div>
        """, unsafe_allow_html=True)
def main_app():
    inject_css()
    c_df, q_df, users_df = load_db("Sheet1"), load_db("questions"), load_db("users")
    user_row = users_df[users_df['username'] == st.session_state.username]
    is_admin = (st.session_state.role == "admin")
    membership = user_row.iloc[0].get('membership', 'free') if not user_row.empty else "free"
    is_pro = (membership == "pro")

    # 在線狀態 Heartbeat
    if time.time() - st.session_state.get('last_sync', 0) > 180:
        update_user_data(st.session_state.username, "last_seen", datetime.now().strftime("%H:%M:%S"))
        st.session_state.last_sync = time.time()

    with st.sidebar:
        label = "（ADMIN）" if is_admin else (f"（PRO）：{st.session_state.username}" if is_pro else "（學生）")
        st.markdown(f"### 👋 {st.session_state.username}\n{label}")
        menu = ["📅 本週菜單", "🧪 AI 補給站", "📝 模擬演練", "🏆 排行榜"]
        if is_admin or is_pro:
            st.divider(); st.subheader("🛠️ PRO 工具")
            menu += ["🔬 預埋考點", "🧪 考題開發"]
        if is_admin: menu.append("👤 會員管理")
        choice = st.radio("導航", menu)
        if st.button("🚪 登出"):
            update_user_data(st.session_state.username, "is_online", "FALSE")
            st.session_state.logged_in = False; st.rerun()

    # --- 功能區 ---
    if choice == "📅 本週菜單":
        st.title("🚀 本週重點")
        for _, r in c_df.tail(10).iterrows(): show_concept(r)

    elif choice == "🧪 AI 補給站":
        st.title("🧪 AI 邏輯補給站")
        ai_usage = int(float(user_row.iloc[0]['ai_usage'])) if not user_row.empty else 0
        if not is_admin: st.write(f"🔋 能量：{10-ai_usage}/10")
        if ai_usage >= 10 and not is_admin: st.error("能量耗盡")
        else:
            selected = st.selectbox("選概念", ["---"] + c_df['word'].unique().tolist())
            if selected != "---":
                db_row = c_df[c_df['word'] == selected].iloc[0]
                if st.button("🚀 啟動教學"):
                    exp = ai_explain_from_db(db_row)
                    st.session_state.cur_exp, st.session_state.cur_sel = exp, selected
                    if not is_admin: update_user_data(st.session_state.username, "ai_usage", ai_usage+1)
            
            if st.session_state.get("cur_sel") == selected:
                show_pro_paper_with_download(selected, st.session_state.cur_exp)

    elif choice == "🔬 預埋考點" and (is_admin or is_pro):
        st.title("🔬 AI 考點預埋")
        inp, sub = st.text_input("概念"), st.selectbox("科目", SUBJECTS)
        if st.button("🚀 解碼"):
            res = ai_call("輸出 JSON 教學內容", f"{sub} 的 {inp}", tier="paid" if is_pro else "self")
            if res: res.update({"word":inp, "category":sub}); st.session_state.temp_c = res
        if "temp_c" in st.session_state:
            show_concept(st.session_state.temp_c)
            if st.button("💾 存入大資料庫"):
                tag = "（ADMIN）" if is_admin else f"（PRO）：{st.session_state.username}"
                data = st.session_state.temp_c.copy(); data['contributor'] = tag
                if save_to_db(data, "Sheet1"): st.balloons(); del st.session_state.temp_c; st.rerun()

    elif choice == "🧪 考題開發" and (is_admin or is_pro):
        st.title("🧪 AI 考題開發")
        target = st.selectbox("選概念出題", c_df['word'].unique().tolist())
        if st.button("🪄 生成"):
            res = ai_generate_question_from_db(c_df[c_df['word']==target].iloc[0], tier="paid" if is_pro else "self")
            if res: st.session_state.temp_q = res
        if "temp_q" in st.session_state:
            st.write(st.session_state.temp_q)
            if st.button("💾 存入題庫"):
                tag = "（ADMIN）" if is_admin else f"（PRO）：{st.session_state.username}"
                qdata = st.session_state.temp_q.copy(); qdata['contributor'] = tag
                if save_to_db(qdata, "questions"): st.success("存入"); del st.session_state.temp_q; st.rerun()

    elif choice == "👤 會員管理" and is_admin:
        st.title("👤 成員管理")
        for i, r in load_db("users").iterrows():
            if r['role'] == "admin": continue
            c1, c2, c3 = st.columns([2,1,1])
            c1.write(f"**{r['username']}** ({'🟢' if r['is_online']=='TRUE' else '🔴'})")
            if c2.button("升/降級", key=f"mem_{i}"):
                update_user_data(r['username'], "membership", "pro" if r['membership']=="free" else "free")
                st.rerun()
            if c3.button("補能", key=f"f_{i}"): update_user_data(r['username'], "ai_usage", 0); st.rerun()

# ==========================================
# 7. 執行入口
# ==========================================
def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if not st.session_state.logged_in: login_page()
    else: main_app()

if __name__ == "__main__": main()
