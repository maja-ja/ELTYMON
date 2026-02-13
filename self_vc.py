import streamlit as st
import pandas as pd
import datetime
import time
import json
import base64
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
import markdown
import uuid
import re
import random
import time
import PyPDF2
from PIL import Image

# ==========================================
# 核心配置與 CSS
# ==========================================
st.set_page_config(page_title="備考戰情室 Pro", page_icon="🛡️", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&family=JetBrains+Mono:wght@400&display=swap');
            
            :root { --primary: #FF4B4B; --bg-secondary: #f0f2f6; --glass: rgba(255, 255, 255, 0.9); }
            
            html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }
            .stCodeBlock { font-family: 'JetBrains Mono', monospace; }

            /* 儀表板卡片 */
            .metric-card {
                background: white; border-radius: 12px; padding: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center;
                border-top: 5px solid var(--primary); margin-bottom: 20px;
            }
            .metric-value { font-size: 2.5rem; font-weight: 800; color: #333; }
            .metric-label { font-size: 1rem; color: #666; font-weight: 500; }

            /* 題目卡片 */
            .quiz-card {
                background: #ffffff; border: 1px solid #e0e0e0; border-radius: 10px;
                padding: 25px; margin-bottom: 20px;
            }
            
            /* 玻璃櫃展示區 */
            .glass-cabinet {
                background: rgba(255, 255, 255, 0.8);
                backdrop-filter: blur(10px);
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 15px;
                padding: 20px;
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.15);
            }

            /* 加油按鈕區 */
            .cheer-section { text-align: center; margin-top: 20px; padding: 10px; background: #fff0f0; border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 工具函式：權限與資料庫
# ==========================================

def get_db_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def check_admin():
    """檢查是否為管理員 (輸入密碼)"""
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    
    if st.session_state.is_admin:
        return True
    
    # 密碼輸入框
    with st.expander("🔐 管理員登入 (編輯模式)", expanded=False):
        pwd = st.text_input("輸入密碼解鎖排程與刪除功能", type="password", key="admin_pwd_input")
        if pwd:
            if pwd == st.secrets.get("ADMIN_PASSWORD", "1234"): # 預設1234
                st.session_state.is_admin = True
                st.success("🔓 解鎖成功！")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("❌ 密碼錯誤")
    return False

# ==========================================
# AI 核心引擎 (多 Key 輪詢)
# ==========================================
def run_gemini_robust(prompt, images=None, model_name='gemini-2.0-flash'):
    keys = st.secrets.get("GEMINI_KEYS")
    if not keys:
        single_key = st.secrets.get("GEMINI_API_KEY")
        keys = [single_key] if single_key else []
        if not keys:
            st.error("❌ 找不到 API Keys")
            return None

    if isinstance(keys, str): keys = [keys]
    
    image_list = images if isinstance(images, list) else ([images] if images else [])
    
    shuffled_keys = list(keys).copy()
    random.shuffle(shuffled_keys)
    
    last_error = "Unknown"
    for api_key in shuffled_keys:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            content_parts = [prompt]
            if image_list: content_parts.extend(image_list)
            
            response = model.generate_content(content_parts)
            if response and response.text:
                return response.text
            else:
                last_error = "Empty Response"
                continue
        except Exception as e:
            last_error = str(e)
            time.sleep(0.5)
            continue
            
    st.error(f"❌ AI 呼叫失敗: {last_error}")
    return None

def run_gemini(prompt):
    return run_gemini_robust(prompt)

# ==========================================
# 1. 模組：戰情儀表板 (Dashboard)
# ==========================================
def dashboard_page():
    st.title("🛡️ 備考戰情室 (Mission Control)")
    
    # 讀取加油數據 (模擬或從 Sheet 讀取)
    conn = get_db_connection()
    try:
        # 嘗試讀取一個 meta 表，若無則建立
        meta_df = conn.read(worksheet="meta_data", ttl=0)
    except:
        meta_df = pd.DataFrame([{"key": "cheers", "value": 0}, {"key": "pokes", "value": 0}])
    
    cheers_count = int(meta_df[meta_df['key']=="cheers"]['value'].iloc[0]) if not meta_df.empty else 0
    pokes_count = int(meta_df[meta_df['key']=="pokes"]['value'].iloc[0]) if not meta_df.empty else 0

    # 頂部狀態列
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.markdown(f"### 👋 歡迎來到戰情室！")
        st.caption("這裡是全公開的備考監督平台。訪客請隨意參觀，並點擊右側按鈕給予支持！")
    with c2:
        st.metric("🎈 收到的加油", f"{cheers_count} 次")
    with c3:
        st.metric("👉 收到的督促", f"{pokes_count} 次")

    st.divider()

    # 1. 倒數計時
    targets = [
        {"name": "生物奧林匹亞", "date": "2026-11-01"},
        {"name": "學測", "date": "2027-01-20"},
    ]
    cols = st.columns(len(targets))
    for i, target in enumerate(targets):
        t_date = datetime.datetime.strptime(target['date'], "%Y-%m-%d").date()
        days_left = (t_date - datetime.date.today()).days
        with cols[i]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{target['name']}</div>
                <div class="metric-value" style="color: {'#d9534f' if days_left < 30 else '#333'}">
                    {days_left} <span style="font-size:1rem">天</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 2. 任務清單 (ReadOnly for Guests, Edit for Admin)
    st.subheader("📅 今日任務狀態")
    try:
        tasks_df = conn.read(worksheet="tasks", ttl=0)
        if 'status' not in tasks_df.columns: tasks_df['status'] = False
        tasks_df['status'] = tasks_df['status'].fillna(False).astype(bool)
        
        # 權限判斷
        is_admin = check_admin()
        
        if is_admin:
            edited_df = st.data_editor(
                tasks_df, num_rows="dynamic", use_container_width=True,
                column_config={"status": st.column_config.CheckboxColumn("完成", default=False)}
            )
            if st.button("💾 更新任務"):
                conn.update(worksheet="tasks", data=edited_df)
                st.success("已更新！")
        else:
            # 訪客模式：唯讀顯示 (美化版)
            st.dataframe(tasks_df, use_container_width=True, hide_index=True)
            st.caption("🔒 此表僅供檢視，輸入密碼後可編輯。")

    except Exception as e:
        st.warning("資料庫連線中...")

# ==========================================
# 2. 模組：智能排程 (Glass Cabinet Scheduler)
# ==========================================
def scheduler_page():
    st.title("📅 智能排程中心 (Glass Cabinet)")
    st.caption("公開透明的讀書計畫。訪客可查看，本人憑密碼修改。")
    
    conn = get_db_connection()
    is_admin = check_admin() # 檢查權限
    
    # 讀取資料
    try:
        plan_df = conn.read(worksheet="study_plan", ttl=0)
    except:
        plan_df = pd.DataFrame(columns=['id', 'subject', 'topic', 'status'])

    # --- 玻璃櫃展示區 (所有人可見) ---
    st.markdown("### 🔍 本週展示櫃")
    
    # 這裡假設 session_state 有存當週課表，或是從 DB 讀取
    # 為了演示，我們簡單做一個過濾 Pending 的顯示
    
    pending_tasks = plan_df[plan_df['status'] == "Pending"].head(10)
    
    # CSS 美化展示
    st.markdown("""
    <div class="glass-cabinet">
        <h3 style="text-align:center; color:#555;">✨ 本週黃金目標 ✨</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px;">
    """, unsafe_allow_html=True)
    
    for idx, row in pending_tasks.iterrows():
        color = "#e3f2fd" if row['subject'] == "Eng" else "#e8f5e9"
        icon = "🧬" if row['subject'] == "Bio" else "🌍"
        st.markdown(f"""
            <div style="background:{color}; padding:15px; border-radius:10px; border-left:5px solid #ccc;">
                <div style="font-weight:bold; font-size:1.1em;">{icon} {row['subject']}</div>
                <div style="font-size:0.9em; margin-top:5px;">{row['topic']}</div>
            </div>
        """, unsafe_allow_html=True)
        
    st.markdown("</div></div>", unsafe_allow_html=True)

    st.divider()

    # --- 控制台 (僅管理員可見) ---
    if is_admin:
        st.subheader("⚙️ 排程控制台 (Admin Only)")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**新增任務 / AI 排程**")
            new_topic = st.text_input("輸入新單元名稱")
            if st.button("➕ 加入待辦"):
                new_row = pd.DataFrame([{"id": str(uuid.uuid4())[:6], "subject": "General", "topic": new_topic, "status": "Pending"}])
                updated = pd.concat([plan_df, new_row], ignore_index=True)
                conn.update(worksheet="study_plan", data=updated)
                st.rerun()
        with col2:
            st.markdown("**管理資料庫**")
            st.dataframe(plan_df, height=200)
    else:
        st.info("🔒 排程調整功能已鎖定。若您是本人，請在上方解鎖。")

# ==========================================
# 3. 模組：AI 命題工廠 (開放讀書區)
# ==========================================
def exam_factory_page():
    st.title("🏭 AI 命題工廠 (Open Factory)")
    st.caption("開放區域：任何人都可以上傳筆記或圖片，幫我生成題目並存入題庫！")
    
    # 這是開放區，不需要密碼
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 1. 投料區 (Input)")
        subject = st.selectbox("科目", ["🧬 生物奧林匹亞", "🌍 托福", "💼 多益", "🧪 自然科學"])
        context_text = st.text_area("文字筆記", placeholder="貼上筆記內容或錯題觀念...")
        uploaded_files = st.file_uploader("上傳圖片素材", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        
        contributor_name = st.text_input("貢獻者留名 (選填)", placeholder="你的名字/暱稱")
        
        generate_btn = st.button("🚀 啟動 AI 出題", type="primary", use_container_width=True)

    with col2:
        st.markdown("#### 2. 產出預覽 (Preview)")
        
        if generate_btn:
            image_payloads = [Image.open(f) for f in uploaded_files] if uploaded_files else []
            
            with st.spinner("🤖 AI 正在分析素材並出題中..."):
                prompt = f"""
                角色：嚴格的考試出題官。
                科目：{subject}。
                內容：{context_text}。
                任務：出一題高難度單選題。
                格式：JSON {{ "q": "題目", "options": ["A","B","C","D"], "answer": "A", "explanation": "詳解" }}
                """
                res = run_gemini_robust(prompt, images=image_payloads)
                
                if res:
                    try:
                        clean_json = re.sub(r"```json|```", "", res).strip()
                        q_data = json.loads(clean_json)
                        st.session_state.temp_q = q_data
                        st.session_state.temp_contributor = contributor_name or "Anonymous"
                        st.session_state.temp_subject = subject
                    except:
                        st.error("生成失敗，請重試。")

        # 顯示暫存題目
        if "temp_q" in st.session_state:
            q = st.session_state.temp_q
            st.markdown(f"""
            <div class="quiz-card">
                <div style="font-weight:bold; color:#FF4B4B;">{st.session_state.temp_subject}</div>
                <div style="font-size:1.2em; margin:10px 0;">{q['q']}</div>
                <div style="background:#eee; padding:5px;">Ans: {q['answer']}</div>
                <div style="font-size:0.8em; color:#666; margin-top:5px;">由 {st.session_state.temp_contributor} 貢獻</div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("📥 確認入庫 (Save to Bank)"):
                conn = get_db_connection()
                try:
                    bank_df = conn.read(worksheet="quiz_bank", ttl=0)
                except:
                    bank_df = pd.DataFrame(columns=['id', 'date', 'subject', 'question_json', 'is_correct', 'contributor'])
                
                new_row = {
                    "id": str(uuid.uuid4())[:8],
                    "date": datetime.date.today().strftime("%Y-%m-%d"),
                    "subject": st.session_state.temp_subject,
                    "question_json": json.dumps(q, ensure_ascii=False),
                    "is_correct": "Pending",
                    "contributor": st.session_state.temp_contributor
                }
                
                updated = pd.concat([bank_df, pd.DataFrame([new_row])], ignore_index=True)
                conn.update(worksheet="quiz_bank", data=updated)
                st.balloons() # 感謝貢獻者
                st.success("題目已存入競技場！")
                del st.session_state.temp_q

# ==========================================
# 4. 模組：競技場 (Arena & Archive)
# ==========================================
def arena_page():
    st.title("⚔️ 競技場 (The Arena)")
    
    tab1, tab2 = st.tabs(["🔥 戰鬥區 (Pending)", "🏆 榮譽殿堂 (Archive)"])
    
    conn = get_db_connection()
    try:
        bank_df = conn.read(worksheet="quiz_bank", ttl=0)
    except:
        st.warning("題庫為空")
        return

    # --- Tab 1: 刷題區 ---
    with tab1:
        pending_df = bank_df[bank_df['is_correct'] == "Pending"].reset_index(drop=True)
        if pending_df.empty:
            st.success("🎉 目前無待辦題目！請去命題工廠新增。")
        else:
            if "arena_idx" not in st.session_state: st.session_state.arena_idx = 0
            if st.session_state.arena_idx >= len(pending_df): st.session_state.arena_idx = 0
            
            row = pending_df.iloc[st.session_state.arena_idx]
            q_data = json.loads(row['question_json'])
            
            st.markdown(f"**題目來源**: {row.get('contributor', 'System')}")
            st.markdown(f"<div class='question-text'>{q_data['q']}</div>", unsafe_allow_html=True)
            
            with st.form(f"ans_{row['id']}"):
                user_choice = st.radio("選擇", q_data['options'])
                if st.form_submit_button("提交"):
                    ans_char = user_choice.split(".")[0] if user_choice else ""
                    correct = (ans_char == q_data['answer'])
                    
                    if correct:
                        st.balloons()
                        st.success("✅ 正確！")
                        # 更新 DB
                        bank_df.loc[bank_df['id'] == row['id'], 'is_correct'] = "TRUE"
                        bank_df.loc[bank_df['id'] == row['id'], 'user_answer'] = ans_char
                    else:
                        st.error(f"❌ 錯誤，答案是 {q_data['answer']}")
                        bank_df.loc[bank_df['id'] == row['id'], 'is_correct'] = "FALSE"
                        bank_df.loc[bank_df['id'] == row['id'], 'user_answer'] = ans_char
                    
                    conn.update(worksheet="quiz_bank", data=bank_df)
                    time.sleep(1)
                    st.rerun()

    # --- Tab 2: 已寫題區觀賞 (Archive) ---
    with tab2:
        st.subheader("🏛️ 歷史戰績博物館")
        st.caption("這裡展示已經被攻克的題目，訪客可自由瀏覽。")
        
        finished_df = bank_df[bank_df['is_correct'] != "Pending"].sort_values(by="date", ascending=False)
        
        if finished_df.empty:
            st.info("尚無歷史紀錄")
        else:
            for i, row in finished_df.iterrows():
                q = json.loads(row['question_json'])
                status_color = "green" if row['is_correct'] == "TRUE" else "red"
                status_icon = "✅" if row['is_correct'] == "TRUE" else "❌"
                
                with st.expander(f"{status_icon} {row['date']} - {row['subject']} (by {row.get('contributor', 'Unknown')})"):
                    st.markdown(f"""
                    **Q:** {q['q']}  
                    **你的回答:** `{row.get('user_answer', '')}` | **正解:** `{q['answer']}`  
                    **解析:** {q.get('explanation', '無')}
                    """)

# ==========================================
# 5. 主程式與側邊欄 (Cheer Section)
# ==========================================
def main():
    inject_custom_css()
    
    with st.sidebar:
        st.title("🛡️ 戰情室導航")
        page = st.radio("Go to", ["戰情儀表板", "智能排程 (Glass)", "AI 命題工廠 (Open)", "競技場 (Arena)"])
        
        st.markdown("---")
        
        # === 督促與加油按鈕區 ===
        st.markdown("### 💪 訪客互動區")
        st.caption("按下去，我會收到通知！")
        
        col_cheer, col_poke = st.columns(2)
        
        conn = get_db_connection()
        
        # 讀取當前計數 (為了更新用)
        try:
            meta_df = conn.read(worksheet="meta_data", ttl=0)
            if meta_df.empty: raise Exception
        except:
            meta_df = pd.DataFrame([{"key": "cheers", "value": 0}, {"key": "pokes", "value": 0}])

        with col_cheer:
            if st.button("🎈 加油", use_container_width=True):
                st.balloons() # 讓按的人看到氣球
                curr = int(meta_df[meta_df['key']=="cheers"]['value'].iloc[0])
                meta_df.loc[meta_df['key']=="cheers", "value"] = curr + 1
                conn.update(worksheet="meta_data", data=meta_df)
                st.toast("已發送加油！", icon="🎈")
        
        with col_poke:
            if st.button("👉 督促", use_container_width=True):
                st.snow() # 另一種特效
                curr = int(meta_df[meta_df['key']=="pokes"]['value'].iloc[0])
                meta_df.loc[meta_df['key']=="pokes", "value"] = curr + 1
                conn.update(worksheet="meta_data", data=meta_df)
                st.toast("已發送督促訊號！", icon="😤")
                
        st.markdown("---")
        st.caption("訪客模式 / 管理員登入請至功能頁")

    if page == "戰情儀表板":
        dashboard_page()
    elif page == "智能排程 (Glass)":
        scheduler_page()
    elif page == "AI 命題工廠 (Open)":
        exam_factory_page()
    elif page == "競技場 (Arena)":
        arena_page()

if __name__ == "__main__":
    main()
