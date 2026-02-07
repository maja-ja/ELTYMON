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
        target_keys, model_name = [st.secrets.get("GEMINI_SELF_KEY")], "gemini-1.5-pro"
    elif tier == "paid":
        target_keys, model_name = st.secrets.get("GEMINI_PAID_KEYS", []), "gemini-1.5-pro"
    else:
        target_keys, model_name = get_api_keys(), "gemini-1.5-flash"

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
    prompt = f"你現在是命題委員。請根據概念「{db_row['word']}」出題。要求：LaTeX 格式、情境化、JSON 輸出。"
    return ai_call("JSON 格式輸出題目", prompt, tier=tier)

def ai_explain_from_db(db_row):
    prompt = f"概念：{db_row['word']} | 定義：{db_row['definition']} | 公式：{db_row['roots']}。請深度教學。"
    return ai_call(prompt, tier="free")

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
    with c1: st.info(f"🧬 **核心邏輯**\n\n{row['roots']}"); st.success(f"🧠 **記憶點**\n\n{row['memory_hook']}")
    with c2: st.warning(f"🚩 **雷區**\n\n{row['native_vibe']}"); with st.expander("🔍 詳細拆解"): st.write(row['breakdown'])

def show_pro_paper_with_download(title, content):
    js_title, js_content = json.dumps(title, ensure_ascii=False), json.dumps(content, ensure_ascii=False)
    div_id = f"paper_{int(time.time())}"
    html_code = f"""
    <div id="{div_id}_wrapper" style="background:#1e1e1e; padding:20px; border-radius:15px; border:1px solid #333; color:white;">
        <div id="{div_id}_content">載入中...</div>
        <hr><button id="{div_id}_btn" style="width:100%; padding:12px; background:#6366f1; color:white; border:none; border-radius:10px; cursor:pointer;">📥 下載精美講義 (PDF)</button>
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
                const container = document.createElement('div');
                container.style.cssText = "width:210mm; background:white; color:black; padding:20mm; font-family:sans-serif;";
                container.innerHTML = `<h1 style="color:#1e3a8a; border-bottom:2px solid #6366f1;">⚡ 116 講義: ${{title}}</h1><br>${{marked.parse(content)}}`;
                renderMathInElement(container, {{ delimiters: [{{left: "$$", right: "$$", display: true}}, {{left: "$", right: "$", display: false}}] }});
                html2pdf().set({{ margin:10, filename: title+".pdf", jsPDF:{{format:'a4'}} }}).from(container).save();
            }};
        }})();
    </script>"""
    st.components.v1.html(html_code, height=500, scrolling=True)

# ==========================================
# 5. 頁面邏輯 (登入/主程式)
# ==========================================
def login_page():
    st.title("⚡ Kadowsella 116 登入")
    tab1, tab2 = st.tabs(["🔑 登入", "📝 註冊"])
    with tab1:
        with st.form("login"):
            u, p = st.text_input("帳號"), st.text_input("密碼", type="password")
            if st.form_submit_button("進入戰情室"):
                users = load_db("users")
                user = users[(users['username'] == u) & (users['password'] == hash_password(p))]
                if not user.empty:
                    st.session_state.logged_in, st.session_state.username, st.session_state.role = True, u, user.iloc[0]['role']
                    update_user_data(u, "is_online", "TRUE")
                    st.rerun()
                else: st.error("❌ 錯誤")
    with tab2:
        with st.form("reg"):
            nu, np, code = st.text_input("帳號"), st.text_input("密碼", type="password"), st.text_input("邀請碼", type="password")
            if st.form_submit_button("註冊"):
                is_admin = (code == st.secrets.get("ADMIN_PASSWORD"))
                if save_to_db({"username":nu, "password":hash_password(np), "role":"admin" if is_admin else "student", "membership":"pro" if is_admin else "free", "ai_usage":0}, "users"):
                    st.success("成功")

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
