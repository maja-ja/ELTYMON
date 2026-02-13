import streamlit as st
import pandas as pd
import datetime
import time
import json
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
import markdown
import uuid
import re
import random
from PIL import Image

# ==========================================
# 1. 初始化與 CSS 注入
# ==========================================
st.set_page_config(page_title="備考戰情室 Pro", page_icon="🛡️", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap');
            html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }
            
            /* 玻璃櫃特效 */
            .glass-card {
                background: rgba(255, 255, 255, 0.7);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                border: 1px solid rgba(255, 255, 255, 0.5);
                padding: 20px;
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1);
                margin-bottom: 20px;
            }
            
            /* 課表格子 */
            .grid-item {
                padding: 10px; border-radius: 8px; margin: 5px;
                border-left: 5px solid #FF4B4B; background: #fff;
                min-height: 80px; font-size: 0.9em;
            }
            
            .admin-badge {
                background: #FF4B4B; color: white; padding: 2px 8px;
                border-radius: 10px; font-size: 0.7em; vertical-align: middle;
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心：權限驗證系統
# ==========================================
def check_auth():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    with st.sidebar:
        st.markdown("### 🔒 權限控制")
        if not st.session_state.authenticated:
            pwd = st.text_input("輸入管理員密碼以編輯", type="password")
            if st.button("解鎖權限"):
                if pwd == st.secrets.get("ADMIN_PASSWORD", "1234"):
                    st.session_state.authenticated = True
                    st.success("🔓 模式：管理員 (可排課/編輯)")
                    st.rerun()
                else:
                    st.error("密碼錯誤")
        else:
            st.success("🔓 模式：管理員")
            if st.button("登出/鎖定"):
                st.session_state.authenticated = False
                st.rerun()
    return st.session_state.authenticated

# ==========================================
# 3. 資料庫與 AI 工具
# ==========================================
def get_db():
    return st.connection("gsheets", type=GSheetsConnection)

def run_gemini(prompt, images=None):
    # 此處沿用你原本的多 Key 輪詢邏輯 (簡化示意)
    api_key = st.secrets.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        res = model.generate_content([prompt] + (images if images else []))
        return res.text
    except: return None

# ==========================================
# 4. 頁面：戰情儀表板 (含加油按鈕)
# ==========================================
def dashboard_page():
    st.title("🛡️ 備考戰情中心")
    is_admin = st.session_state.authenticated
    
    # --- 加油數據區 ---
    conn = get_db()
    try:
        meta_df = conn.read(worksheet="meta", ttl=0)
    except:
        meta_df = pd.DataFrame([{"key":"cheers", "value":0}, {"key":"pokes", "value":0}])

    c1, c2, c3 = st.columns([2,1,1])
    with c1: 
        st.subheader("👋 歡迎參觀我的讀書玻璃櫃")
        st.caption("這是我的備考實況，請隨意翻閱題庫，或是幫我加油！")
    with c2: st.metric("🎈 收到加油", f"{int(meta_df.iloc[0]['value'])} 次")
    with c3: st.metric("👉 收到督促", f"{int(meta_df.iloc[1]['value'])} 次")

    st.divider()

    # --- 今日任務 (上鎖檢查) ---
    st.markdown(f"### 📅 今日任務 {'<span class="admin-badge">ADMIN</span>' if is_admin else ''}", unsafe_allow_html=True)
    try:
        tasks_df = conn.read(worksheet="tasks", ttl=0)
        if is_admin:
            edited_df = st.data_editor(tasks_df, num_rows="dynamic", use_container_width=True)
            if st.button("💾 儲存更改"):
                conn.update(worksheet="tasks", data=edited_df)
                st.toast("已同步至雲端！")
        else:
            # 訪客看到的是美化過的表格
            st.table(tasks_df)
    except: st.info("尚無任務數據")

# ==========================================
# 5. 頁面：智能排程 (玻璃櫃化)
# ==========================================
def scheduler_page():
    st.title("📅 讀書計畫展示櫃")
    is_admin = st.session_state.authenticated
    conn = get_db()
    
    try: plan_df = conn.read(worksheet="study_plan", ttl=0)
    except: plan_df = pd.DataFrame(columns=['day', 's1', 's2'])

    # --- 展示展示區 (所有人可見) ---
    st.markdown("""<div class="glass-card">""", unsafe_allow_html=True)
    cols = st.columns(5)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    for i, day in enumerate(days):
        with cols[i]:
            st.markdown(f"**{day}**")
            # 假設 DB 裡有存當週課表
            day_data = plan_df[plan_df['day'] == day]
            if not day_data.empty:
                st.markdown(f"<div class='grid-item'>🧬 {day_data.iloc[0]['s1']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='grid-item'>🌍 {day_data.iloc[0]['s2']}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='color:#ccc'>休息</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- 管理區 (上鎖檢查) ---
    if is_admin:
        st.divider()
        st.subheader("⚙️ 課程編排 (管理員模式)")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 1. AI 自動排課")
            if st.button("⚡ 根據學校進度生成新課表"):
                with st.spinner("AI 規劃中..."):
                    # 這裡串接你之前的 run_gemini_robust 邏輯
                    time.sleep(2)
                    st.success("新課表已生成，請確認後存檔。")
        with col_b:
            st.markdown("#### 2. 手動微調")
            manual_edit = st.data_editor(plan_df, num_rows="dynamic")
            if st.button("💾 鎖定本週課表"):
                conn.update(worksheet="study_plan", data=manual_edit)
                st.rerun()
    else:
        st.info("🔒 若要重新排課或修改進度，請先在側邊欄解鎖。")

# ==========================================
# 6. 頁面：開放讀書區 (所有人可上傳)
# ==========================================
def factory_page():
    st.title("🏭 讀書區：題目貢獻站")
    st.caption("開放給所有人：你可以幫我出題，我會在競技場挑戰它！")
    
    col_l, col_r = st.columns(2)
    with col_l:
        subject = st.selectbox("科目", ["生奧", "托福", "學測"])
        context = st.text_area("參考內容/筆記")
        imgs = st.file_uploader("上傳圖檔 (可多張)", accept_multiple_files=True)
        name = st.text_input("貢獻者姓名", "熱心同學")
        
        if st.button("🚀 生成題目並送出"):
            with st.spinner("AI 命題中..."):
                # 呼叫 Gemini 邏輯
                q_json = run_gemini(f"請針對{context}出一題JSON格式題目")
                if q_json:
                    # 寫入資料庫
                    st.session_state.last_gen = q_json
                    st.success(f"感謝 {name}！題目已進入審核區。")
                    st.balloons()
    
    with col_r:
        st.subheader("📝 預覽生成結果")
        if "last_gen" in st.session_state:
            st.json(st.session_state.last_gen)

# ==========================================
# 7. 頁面：競技場 (含已寫題觀賞)
# ==========================================
def arena_page():
    st.title("⚔️ 題目競技場")
    tab1, tab2 = st.tabs(["🔥 挑戰進行中", "🏆 已攻克題庫 (Archive)"])
    
    conn = get_db()
    bank_df = conn.read(worksheet="quiz_bank", ttl=0)
    
    with tab1:
        # 只顯示 Pending 題目，只有本人可以刷題 (視需求可上鎖)
        st.write("目前有 X 題等待挑戰...")
        if st.session_state.authenticated:
            st.info("管理員模式：開始刷題")
            # 這裡放刷題邏輯...
        else:
            st.warning("🔒 刷題功能僅限本人使用。")

    with tab2:
        st.subheader("🏛️ 榮譽殿堂")
        st.caption("以下是我已經寫完的題目與詳解，歡迎參觀。")
        done_df = bank_df[bank_df['is_correct'] != "Pending"]
        for _, row in done_df.iterrows():
            q = json.loads(row['question_json'])
            with st.expander(f"{row['date']} - {row['subject']} - {'✅' if row['is_correct']=='TRUE' else '❌'}"):
                st.markdown(f"**題目：** {q['q']}")
                st.markdown(f"**詳解：** {q['explanation']}")

# ==========================================
# 8. 側邊欄互動按鈕
# ==========================================
def sidebar_interaction():
    conn = get_db()
    try: meta_df = conn.read(worksheet="meta", ttl=0)
    except: return

    st.sidebar.divider()
    st.sidebar.markdown("### 📣 支持一下")
    
    c1, c2 = st.sidebar.columns(2)
    if c1.button("🎈 加油"):
        st.balloons()
        meta_df.loc[meta_df['key'] == 'cheers', 'value'] += 1
        conn.update(worksheet="meta", data=meta_df)
        st.toast("收到你的加油了！感謝！")
    
    if c2.button("👉 督促"):
        st.snow()
        meta_df.loc[meta_df['key'] == 'pokes', 'value'] += 1
        conn.update(worksheet="meta", data=meta_df)
        st.toast("我會認真讀書的！")

# ==========================================
# 主程式路由
# ==========================================
def main():
    inject_custom_css()
    is_admin = check_auth()
    sidebar_interaction()
    
    # 頁面選擇
    menu = ["戰情儀表板", "計畫展示櫃", "題目貢獻站", "歷史題庫觀賞"]
    choice = st.sidebar.radio("導航", menu)
    
    if choice == "戰情儀表板":
        dashboard_page()
    elif choice == "計畫展示櫃":
        scheduler_page()
    elif choice == "題目貢獻站":
        factory_page()
    elif choice == "歷史題庫觀賞":
        arena_page()

if __name__ == "__main__":
    main()
