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
# 0. 核心配置與手機版 CSS 優化
# ==========================================
st.set_page_config(page_title="備考戰情室 Pro", page_icon="🛡️", layout="wide")

def inject_ui_style():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap');
            
            /* 全局字體與背景 */
            html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }
            .main { background-color: #f8f9fa; }

            /* 手機版適應：卡片與字體 */
            @media (max-width: 600px) {
                .metric-value { font-size: 1.8rem !important; }
                .metric-label { font-size: 0.8rem !important; }
                .glass-card { padding: 10px !important; }
            }

            /* 玻璃展示櫃樣式 */
            .glass-card {
                background: rgba(255, 255, 255, 0.8);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                border: 1px solid rgba(255, 255, 255, 0.3);
                padding: 20px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.05);
                margin-bottom: 15px;
            }

            /* 課表格子樣式 */
            .grid-slot {
                background: white; border-radius: 8px; padding: 10px;
                margin-bottom: 8px; border-left: 5px solid #FF4B4B;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.03);
            }
            .bio-slot { border-left-color: #28a745; }
            .eng-slot { border-left-color: #007bff; }
            
            /* 標題與裝飾 */
            .big-event-title { color: #FF4B4B; font-weight: 800; border-bottom: 2px solid #FF4B4B; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 權限驗證系統
# ==========================================
def check_auth():
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    
    with st.sidebar:
        st.markdown("### 🔐 管理模式")
        if not st.session_state.is_admin:
            pwd = st.text_input("輸入密碼以排課", type="password")
            if st.button("解鎖櫃子"):
                if pwd == st.secrets.get("ADMIN_PASSWORD", "1234"): # 密碼可設定在 secrets
                    st.session_state.is_admin = True
                    st.success("🔓 您現在具備編輯權限")
                    st.rerun()
                else:
                    st.error("密碼錯誤")
        else:
            if st.button("🔒 鎖定櫃子"):
                st.session_state.is_admin = False
                st.rerun()
    return st.session_state.is_admin

# ==========================================
# 2. 側邊欄互動按鈕（加油與督促）
# ==========================================
def sidebar_interactions():
    conn = st.connection("gsheets", type=GSheetsConnection)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📣 給我一點力量")
    
    # 讀取雲端計數 (儲存在 meta_data 工作表)
    try:
        meta_df = conn.read(worksheet="meta_data", ttl=0)
    except:
        meta_df = pd.DataFrame([{"key": "cheers", "value": 0}, {"key": "pokes", "value": 0}])

    c1, c2 = st.sidebar.columns(2)
    if c1.button("🎈 加油"):
        st.balloons()
        meta_df.loc[meta_df['key'] == 'cheers', 'value'] += 1
        conn.update(worksheet="meta_data", data=meta_df)
        st.sidebar.toast("收到你的鼓勵了！")

    if c2.button("👉 督促"):
        st.snow()
        meta_df.loc[meta_df['key'] == 'pokes', 'value'] += 1
        conn.update(worksheet="meta_data", data=meta_df)
        st.sidebar.toast("哎呀，被抓到了，我會努力！")

    st.sidebar.caption(f"✨ 累計加油: {int(meta_df[meta_df['key']=='cheers']['value'].iloc[0])} 次")

# ==========================================
# 3. 頁面：戰情儀表板 (包含大記事)
# ==========================================
def dashboard_page():
    st.markdown("<h1 class='big-event-title'>🚩 備考大記事 (Milestones)</h1>", unsafe_allow_html=True)
    
    # 大記事數據
    targets = [
        {"name": "生物奧林匹亞", "date": "2026-11-01", "icon": "🧬"},
        {"name": "托福考試", "date": "2026-12-15", "icon": "🌍"},
        {"name": "學測", "date": "2027-01-20", "icon": "🎓"},
        {"name": "同等學力", "date": "2026-10-01", "icon": "📜"}
    ]
    
    # 倒數計時卡片 (手機版會自動堆疊)
    cols = st.columns(len(targets))
    for i, t in enumerate(targets):
        days_left = (datetime.datetime.strptime(t['date'], "%Y-%m-%d").date() - datetime.date.today()).days
        with cols[i]:
            st.markdown(f"""
            <div class="glass-card" style="text-align:center;">
                <div style="font-size:1.5rem;">{t['icon']}</div>
                <div style="font-size:0.9rem; color:#666;">{t['name']}</div>
                <div class="metric-value" style="font-size:2rem; font-weight:800; color:{'#FF4B4B' if days_left < 30 else '#333'}">
                    {days_left} <span style="font-size:0.8rem">天</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    
    # 今日任務 (共同檢視)
    st.subheader("📅 本日攻堅進度")
    conn = st.connection("gsheets", type=GSheetsConnection)
    is_admin = st.session_state.is_admin
    
    try:
        tasks_df = conn.read(worksheet="tasks", ttl=0)
        if is_admin:
            edited_df = st.data_editor(tasks_df, num_rows="dynamic", use_container_width=True)
            if st.button("💾 更新雲端狀態"):
                conn.update(worksheet="tasks", data=edited_df)
                st.success("同步成功！")
        else:
            # 訪客看到的是美化過的表格
            st.dataframe(tasks_df, use_container_width=True, hide_index=True)
            st.caption("🔒 鎖定中：僅管理員可打勾或新增任務。")
    except:
        st.info("任務清單連線中...")

# ==========================================
# 4. 頁面：計畫展示櫃 (Glass Cabinet)
# ==========================================
def scheduler_page():
    st.title("📅 計畫展示櫃")
    is_admin = st.session_state.is_admin
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    try:
        plan_df = conn.read(worksheet="study_plan", ttl=0)
    except:
        plan_df = pd.DataFrame(columns=['day', 'bio_slot', 'eng_slot'])

    # --- 玻璃模式 (所有人可見) ---
    st.markdown("### 🔍 本週公開路徑")
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    
    # 手機版適應：桌機顯示 5 欄，手機建議顯示垂直或兩欄
    cols = st.columns(5)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    for i, day in enumerate(days):
        with cols[i]:
            st.markdown(f"**{day}**")
            day_data = plan_df[plan_df['day'] == day]
            if not day_data.empty:
                st.markdown(f"<div class='grid-slot bio-slot'>🧬 {day_data.iloc[0]['bio_slot']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='grid-slot eng-slot'>🌍 {day_data.iloc[0]['eng_slot']}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='color:#ccc; padding:10px;'>休息日</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- 編輯模式 (上鎖) ---
    if is_admin:
        st.divider()
        st.subheader("⚙️ 排課控制台 (管理員)")
        edited_plan = st.data_editor(plan_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 確認鎖定課表並發佈"):
            conn.update(worksheet="study_plan", data=edited_plan)
            st.success("新課表已鎖定至玻璃櫃！")
            st.rerun()
    else:
        st.info("🔒 若要重新排課，請至左側側邊欄輸入密碼解鎖。")

# ==========================================
# 5. 頁面：共同讀書區 (Open Study Area)
# ==========================================
def factory_page():
    st.title("🏭 共同讀書區")
    st.caption("開放區域：大家都可以幫我提供素材或出題。")
    
    col_input, col_preview = st.columns([1, 1])
    
    with col_input:
        st.subheader("📤 上傳筆記/圖片")
        contributor = st.text_input("貢獻者", placeholder="你的名字")
        subj = st.selectbox("科目", ["生奧", "英文", "學測理化"])
        note = st.text_area("筆記內容或想考我的觀念")
        imgs = st.file_uploader("上傳圖片素材", accept_multiple_files=True)
        
        if st.button("🚀 生成題目並送入題庫", type="primary"):
            # 這裡串接 AI 命題邏輯 (簡化示意)
            with st.spinner("AI 正在解析素材..."):
                st.balloons()
                st.success("題目已成功存入雲端！我會在競技場挑戰它。")

# ==========================================
# 6. 頁面：榮譽殿堂 (已寫題區)
# ==========================================
def archive_page():
    st.title("🏆 榮譽殿堂 (Honor Hall)")
    st.caption("所有已經挑戰成功的題目與解析，展示在這裡供大家觀賞。")
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        bank_df = conn.read(worksheet="quiz_bank", ttl=0)
        # 只顯示已完成的題目
        done_df = bank_df[bank_df['is_correct'] != "Pending"].sort_values(by="date", ascending=False)
        
        if done_df.empty:
            st.info("目前尚無戰鬥紀錄。")
        else:
            for _, row in done_df.iterrows():
                try:
                    q = json.loads(row['question_json'])
                    icon = "✅" if row['is_correct'] == "TRUE" else "❌"
                    with st.expander(f"{icon} {row['date']} - {row['subject']} ({row.get('topic','未分類')})"):
                        st.markdown(f"**題目：** {q['q']}")
                        st.markdown(f"**解析：** {q.get('explanation','無')}")
                        st.caption(f"貢獻者：{row.get('contributor','系統')}")
                except: continue
    except:
        st.error("讀取題庫失敗。")

# ==========================================
# 主程式導航
# ==========================================
def main():
    inject_ui_style()
    is_admin = check_auth() # 權限鎖
    sidebar_interactions() # 加油按鈕
    
    # 導航選單
    menu = ["戰情儀表板", "計畫展示櫃", "共同讀書區", "榮譽殿堂"]
    choice = st.sidebar.radio("前往", menu)
    
    if choice == "戰情儀表板":
        dashboard_page()
    elif choice == "計畫展示櫃":
        scheduler_page()
    elif choice == "共同讀書區":
        factory_page()
    elif choice == "榮譽殿堂":
        archive_page()

if __name__ == "__main__":
    main()
