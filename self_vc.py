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
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&family=JetBrains+Mono:wght@400&display=swap');
            html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; background-color: #f4f7f9; }
            
            .glass-card {
                background: rgba(255, 255, 255, 0.75);
                backdrop-filter: blur(12px);
                border-radius: 15px;
                border: 1px solid rgba(255, 255, 255, 0.5);
                padding: 15px;
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1);
                margin-bottom: 15px;
            }
            
            .slot-box {
                background: #ffffff; border-radius: 8px; padding: 10px; margin: 8px 0;
                font-size: 0.85rem; box-shadow: 2px 2px 8px rgba(0,0,0,0.05);
                border-left: 6px solid #FF4B4B;
            }
            .bio { border-left-color: #2ecc71; }
            .eng { border-left-color: #3498db; }
            .point-tag { 
                background: #fff3cd; color: #856404; padding: 2px 6px; 
                border-radius: 4px; font-size: 0.75rem; font-weight: bold; margin-top: 5px; display: inline-block;
            }
            
            @media (max-width: 600px) {
                .stMetric { font-size: 0.7rem !important; }
                .milestone-text { font-size: 0.9rem !important; }
                .slot-box { font-size: 0.8rem !important; }
            }
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
            st.success("🔓 模式：管理員")
            if st.button("🔒 鎖定櫃子"):
                st.session_state.is_admin = False
                st.rerun()
    return st.session_state.is_admin

def get_db():
    return st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# 2. 側邊欄互動 (GIF 擴充與加油)
# ==========================================
def sidebar_mood():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💡 今日備考心情")
    mood_gifs = [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/l0HlBO7eyXzSZkJri/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/3o7TKMGpxvF1V3An96/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/drXGoW1iudhzq/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/13HgwGsXF0aiGY/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/26ufnwz3wDUli7GU0/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/l41lI4bYmcsPJX9Go/giphy.gif"
    ]
    st.sidebar.image(random.choice(mood_gifs), use_column_width=True)
    
    if st.sidebar.button("🎈 按一下幫我加油"):
        st.balloons()
        st.toast("收到能量了！") # 修正：移除 .sidebar

# ==========================================
# 3. 頁面：戰情儀表板 (含大記事與進度)
# ==========================================
def dashboard_page():
    st.title("🛡️ 備考戰情儀表板")
    
    # --- 大記事 (Milestones) ---
    st.markdown("### 🚩 重大目標倒數")
    targets = [
        {"n": "生物奧林匹亞", "d": "2026-11-01", "i": "🧬"},
        {"n": "托福考試", "d": "2026-12-15", "i": "🌍"},
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

    # --- 進度觀測 (Progress Tracking) ---
    st.markdown("### 📊 學習進度觀測")
    conn = get_db()
    try:
        prog_df = conn.read(worksheet="progress", ttl=0)
        bio_p = prog_df[prog_df['subject'] == 'Bio']['value'].iloc[0] / 100
        eng_p = prog_df[prog_df['subject'] == 'Eng']['value'].iloc[0] / 100
    except:
        bio_p, eng_p = 0.0, 0.0

    c1, c2 = st.columns(2)
    with c1:
        st.write(f"🧬 生物科進度: {int(bio_p*100)}%")
        st.progress(bio_p)
    with c2:
        st.write(f"🌍 英文科進度: {int(eng_p*100)}%")
        st.progress(eng_p)

    st.divider()
    
    # --- 今日任務 ---
    st.subheader("📅 本日任務 (共同檢視)")
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
# 4. 頁面：計畫展示櫃 (含考點擴充)
# ==========================================
def scheduler_page():
    st.title("📅 計畫展示櫃 (Glass Cabinet)")
    is_admin = st.session_state.is_admin
    conn = get_db()
    
    try:
        plan_df = conn.read(worksheet="study_plan", ttl=0)
    except:
        plan_df = pd.DataFrame(columns=['day', 'bio_slot', 'eng_slot', 'exam_point'])

    required_cols = ['day', 'bio_slot', 'eng_slot', 'exam_point']
    if not all(col in plan_df.columns for col in required_cols):
        if is_admin:
            st.warning("偵測到 Sheet 欄位缺失，點擊下方按鈕初始化結構")
            if st.button("🛠️ 初始化課表結構 (含考點)"):
                init_df = pd.DataFrame([["Mon","","",""],["Tue","","",""],["Wed","","",""],["Thu","","",""],["Fri","","",""]], 
                                      columns=required_cols)
                conn.update(worksheet="study_plan", data=init_df)
                st.rerun()
        else:
            st.error("櫃子整理中，請稍後再來。")
            return

    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    cols = st.columns(len(days))
    for i, day in enumerate(days):
        with cols[i]:
            st.markdown(f"<div style='text-align:center; font-weight:bold;'>{day}</div>", unsafe_allow_html=True)
            day_data = plan_df[plan_df['day'] == day]
            if not day_data.empty:
                row = day_data.iloc[0]
                st.markdown(f"<div class='slot-box bio'>🧬 {row['bio_slot']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='slot-box eng'>🌍 {row['eng_slot']}</div>", unsafe_allow_html=True)
                if row['exam_point']:
                    st.markdown(f"<div class='point-tag'>🎯 {row['exam_point']}</div>", unsafe_allow_html=True)
            else:
                st.caption("休息")
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
# 5. 頁面：共同讀書區 (考點上傳)
# ==========================================
def joint_study_page():
    st.title("🏭 共同讀書區")
    st.caption("開放區域：大家都可以幫我提供題目、筆記或「考點建議」！")
    
    col_up, col_info = st.columns([1.2, 0.8])
    with col_up:
        name = st.text_input("貢獻者", placeholder="您的姓名")
        subj = st.selectbox("科目", ["生奧", "英文", "學測理化"])
        type_up = st.radio("上傳類型", ["題目/筆記素材", "🎯 考點建議"])
        note = st.text_area("內容描述")
        files = st.file_uploader("上傳圖片 (可多張)", accept_multiple_files=True)
        
        if st.button("🚀 確認送出", use_container_width=True):
            st.balloons()
            st.toast(f"感謝 {name}！您的{type_up}已送達。") # 修正：移除 .sidebar
    with col_info:
        st.markdown("### 📢 玩法說明")
        st.info("- 訪客不需要密碼。\n- 看到不錯的題目或考點可以隨時上傳。\n- 這些內容會成為本人的戰鬥養分！")
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
        st.info("這裡展示所有已解決的難題與考點總結。")

if __name__ == "__main__":
    main()
