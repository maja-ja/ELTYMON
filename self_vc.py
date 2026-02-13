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
# 0. 核心配置與手機/玻璃櫃 CSS
# ==========================================
st.set_page_config(page_title="備考展示櫃 Pro", page_icon="🛡️", layout="wide")

def inject_ui_style():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap');
            html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }
            
            /* 玻璃展示櫃效果 */
            .glass-card {
                background: rgba(255, 255, 255, 0.7);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                border: 1px solid rgba(255, 255, 255, 0.4);
                padding: 15px;
                box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
                margin-bottom: 10px;
            }
            
            /* 手機版字體優化 */
            @media (max-width: 600px) {
                .stMetric { font-size: 0.8rem !important; }
                .milestone-text { font-size: 1rem !important; }
            }

            /* 課表 Slot */
            .slot-box {
                background: #ffffff; border-left: 5px solid #FF4B4B;
                padding: 8px; border-radius: 5px; margin: 5px 0;
                font-size: 0.9rem; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
            }
            .bio { border-left-color: #28a745; }
            .eng { border-left-color: #007bff; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 權限與連線工具
# ==========================================
def check_auth():
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    with st.sidebar:
        st.markdown("### 🔐 玻璃櫃管理員")
        if not st.session_state.is_admin:
            pwd = st.text_input("輸入解鎖密碼", type="password")
            if st.button("解鎖櫃子"):
                if pwd == st.secrets.get("ADMIN_PASSWORD", "1234"):
                    st.session_state.is_admin = True
                    st.rerun()
                else: st.error("密碼錯誤")
        else:
            if st.button("🔒 鎖定櫃子"):
                st.session_state.is_admin = False
                st.rerun()
    return st.session_state.is_admin

def get_db():
    return st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# 2. 側邊欄互動 (GIF 與 加油)
# ==========================================
def sidebar_mood():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💡 今日心情 GIF")
    # 這裡放一些備考專用的 GIF 連結
    mood_gifs = [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/l0HlBO7eyXzSZkJri/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/3o7TKMGpxvF1V3An96/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/drXGoW1iudhzq/giphy.gif"
    ]
    st.sidebar.image(random.choice(mood_gifs))
    
    if st.sidebar.button("🎈 按一下幫我加油"):
        st.balloons()
        st.sidebar.toast("收到能量了！")

# ==========================================
# 3. 頁面：戰情儀表板 (含大記事與進度)
# ==========================================
def dashboard_page():
    st.title("🛡️ 備考戰情儀表板")
    
    # --- 大記事 (Milestones) ---
    st.markdown("### 🚩 重大目標倒數")
    targets = [
        {"n": "生物奧林匹亞", "d": "2026-11-01", "i": "🧬"},
        {"n": "學測", "d": "2027-01-20", "i": "🎓"}
    ]
    cols = st.columns(len(targets))
    for i, t in enumerate(targets):
        days = (datetime.datetime.strptime(t['d'], "%Y-%m-%d").date() - datetime.date.today()).days
        with cols[i]:
            st.markdown(f"""
            <div class="glass-card" style="text-align:center;">
                <span style="font-size:1.5rem;">{t['i']}</span><br>
                <b class="milestone-text">{t['n']}</b><br>
                <span style="font-size:2rem; color:#FF4B4B;">{days}</span> 天
            </div>
            """, unsafe_allow_html=True)

    # --- 進度條 (Progress 編排) ---
    st.markdown("### 📊 學習進度觀測")
    c1, c2 = st.columns(2)
    with c1:
        st.write("🧬 生物科進度 (Campbell)")
        st.progress(0.65, text="65% (已完成 12/20 章)")
    with c2:
        st.write("🌍 英文科進度 (TOEFL/Vocab)")
        st.progress(0.40, text="40% (已完成 2000/5000 單)")

    st.divider()
    
    # --- 今日任務 ---
    st.subheader("📅 本日任務 (共同檢視)")
    conn = get_db()
    try:
        tasks_df = conn.read(worksheet="tasks", ttl=0)
        if st.session_state.is_admin:
            edited = st.data_editor(tasks_df, num_rows="dynamic", use_container_width=True)
            if st.button("💾 同步今日進度"):
                conn.update(worksheet="tasks", data=edited)
                st.success("更新成功！")
        else:
            st.dataframe(tasks_df, use_container_width=True, hide_index=True)
    except: st.info("正在準備任務資料...")

# ==========================================
# 4. 頁面：計畫展示櫃 (修正 KeyError)
# ==========================================
def scheduler_page():
    st.title("📅 計畫展示櫃 (Glass Cabinet)")
    is_admin = st.session_state.is_admin
    conn = get_db()
    
    try:
        plan_df = conn.read(worksheet="study_plan", ttl=0)
    except:
        plan_df = pd.DataFrame(columns=['day', 'bio_slot', 'eng_slot'])

    # --- 關鍵修正：檢查欄位是否存在 ---
    if 'day' not in plan_df.columns:
        if is_admin:
            st.warning("偵測到 Sheet 欄位缺失，點擊下方按鈕初始化")
            if st.button("🛠️ 初始化課表結構"):
                init_df = pd.DataFrame([["Mon","",""],["Tue","",""],["Wed","",""],["Thu","",""],["Fri","",""]], 
                                      columns=['day', 'bio_slot', 'eng_slot'])
                conn.update(worksheet="study_plan", data=init_df)
                st.rerun()
        else:
            st.error("櫃子整理中，請稍後再來。")
            return

    # --- 玻璃櫃展示 (手機適應) ---
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    cols = st.columns(len(days))
    for i, day in enumerate(days):
        with cols[i]:
            st.markdown(f"**{day}**")
            # 這裡就不會報 KeyError 了
            day_data = plan_df[plan_df['day'] == day]
            if not day_data.empty:
                st.markdown(f"<div class='slot-box bio'>{day_data.iloc[0]['bio_slot']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='slot-box eng'>{day_data.iloc[0]['eng_slot']}</div>", unsafe_allow_html=True)
            else:
                st.caption("空")
    st.markdown("</div>", unsafe_allow_html=True)

    if is_admin:
        st.divider()
        st.subheader("⚙️ 排課控制面板")
        new_plan = st.data_editor(plan_df, use_container_width=True)
        if st.button("💾 發佈新計畫"):
            conn.update(worksheet="study_plan", data=new_plan)
            st.success("計畫已發佈到玻璃櫃！")
            st.rerun()

# ==========================================
# 5. 頁面：共同讀書區 (所有人上傳)
# ==========================================
def joint_study_page():
    st.title("🏭 共同讀書區")
    st.caption("這是一個開放區域，任何人都可以幫我提供題目或筆記素材！")
    
    col_up, col_info = st.columns([1.2, 0.8])
    with col_up:
        name = st.text_input("貢獻者", placeholder="您的姓名")
        subj = st.selectbox("科目", ["生奧", "英文", "學測理化"])
        note = st.text_area("上傳觀念筆記或題目內容")
        files = st.file_uploader("上傳圖片 (可多張)", accept_multiple_files=True)
        
        if st.button("🚀 確認送出", use_container_width=True):
            st.balloons()
            st.success("成功！題目將進入後台由 AI 轉化。")
    with col_info:
        st.markdown("""
        ### 📢 玩法說明
        - 訪客不需要密碼。
        - 看到不錯的題目可以拍照上傳。
        - 這些題目會出現在本人的「競技場」中。
        """)
        st.image("https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/3o7TKSjPAnuC28cAnS/giphy.gif")

# ==========================================
# 6. 主程式進入點
# ==========================================
def main():
    inject_ui_style()
    is_admin = check_auth()
    sidebar_mood()
    
    menu = ["🚩 儀表板", "📅 計畫展示", "🏭 共同讀書區", "🏆 榮譽殿堂"]
    choice = st.sidebar.radio("導航中心", menu)
    
    if choice == "🚩 儀表板":
        dashboard_page()
    elif choice == "📅 計畫展示":
        scheduler_page()
    elif choice == "🏭 共同讀書區":
        joint_study_page()
    elif choice == "🏆 榮譽殿堂":
        st.title("🏆 榮譽殿堂")
        st.info("這裡展示所有已解決的難題，即將開放。")

if __name__ == "__main__":
    main()
