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
# 0. 核心配置與全中文 CSS 優化
# ==========================================
st.set_page_config(page_title="備考展示櫃 Pro (中文協作版)", page_icon="🛡️", layout="wide")

def inject_ui_style():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap');
            
            html, body, [class*="css"] { 
                font-family: 'Noto Sans TC', sans-serif !important; 
                background-color: #f4f7f9; 
            }
            
            .glass-card {
                background: rgba(255, 255, 255, 0.8);
                backdrop-filter: blur(12px);
                border-radius: 15px;
                border: 1px solid rgba(255, 255, 255, 0.5);
                padding: 15px;
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1);
                margin-bottom: 15px;
            }
            
            .slot-box {
                background: #ffffff; border-radius: 8px; padding: 10px; margin: 8px 0;
                font-size: 0.9rem; box-shadow: 2px 2px 8px rgba(0,0,0,0.05);
                border-left: 6px solid #FF4B4B;
                color: #333;
            }
            .bio { border-left-color: #2ecc71; }
            .eng { border-left-color: #3498db; }
            
            .point-tag { 
                background: #fff3cd; color: #856404; padding: 4px 8px; 
                border-radius: 4px; font-size: 0.8rem; font-weight: bold; 
                margin-top: 5px; display: inline-block;
            }
            
            .collab-area {
                background: #ffffff; border: 2px dashed #FF4B4B; 
                border-radius: 10px; padding: 20px; margin-top: 20px;
            }

            @media (max-width: 600px) {
                .stMetric { font-size: 0.8rem !important; }
                .slot-box { font-size: 0.85rem !important; }
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
        st.markdown("### 🔐 管理員登入")
        if not st.session_state.is_admin:
            pwd = st.text_input("輸入密碼 (僅限管理功能)", type="password")
            if st.button("解鎖高級權限"):
                if pwd == st.secrets.get("ADMIN_PASSWORD", "1234"):
                    st.session_state.is_admin = True
                    st.rerun()
                else: st.error("密碼錯誤")
        else:
            st.success("🔓 模式：管理員")
            if st.button("🔒 鎖定權限"):
                st.session_state.is_admin = False
                st.rerun()
    return st.session_state.is_admin

def get_db():
    return st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# 2. 側邊欄互動 (GIF 庫擴充)
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
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/l41lI4bYmcsPJX9Go/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/3o7TKSjPAnuC28cAnS/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/l2JhpjQFpL3JJ2AA8/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/5GoVLqeAOo6PK/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/XIqCQ6ra121S8/giphy.gif"
    ]
    st.sidebar.image(random.choice(mood_gifs), use_column_width=True)
    
    if st.sidebar.button("🎈 按一下幫我加油"):
        st.balloons()
        st.toast("收到能量了！感謝支持！")

# ==========================================
# 3. 頁面：戰情儀表板 (進度無則打零)
# ==========================================
def dashboard_page():
    st.title("🛡️ 備考戰情儀表板")
    
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

    st.markdown("### 📊 學習進度觀測")
    conn = get_db()
    try:
        prog_df = conn.read(worksheet="progress", ttl=0)
        bio_val = prog_df[prog_df['科目'] == '生物']['進度'].iloc[0] if not prog_df[prog_df['科目'] == '生物'].empty else 0
        eng_val = prog_df[prog_df['科目'] == '英文']['進度'].iloc[0] if not prog_df[prog_df['科目'] == '英文'].empty else 0
    except:
        bio_val, eng_val = 0, 0 # 進度如果沒有就打零

    c1, c2 = st.columns(2)
    with c1:
        st.write(f"🧬 生物科進度: {bio_val}%")
        st.progress(float(bio_val) / 100)
    with c2:
        st.write(f"🌍 英文科進度: {eng_val}%")
        st.progress(float(eng_val) / 100)

    st.divider()
    
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
# 4. 頁面：計畫展示櫃 (開放幫我排課表)
# ==========================================
def scheduler_page():
    st.title("📅 計畫展示櫃 (開放協作版)")
    st.markdown("### 🤝 開放幫我排課表")
    st.info("這是一個公開的玻璃櫃，任何人都可以直接在下方表格輸入中文，幫我安排本週的進度與考點！")
    
    conn = get_db()
    try:
        plan_df = conn.read(worksheet="study_plan", ttl=0)
    except:
        plan_df = pd.DataFrame(columns=['星期', '生物進度', '英文進度', '🎯考點提醒', '排課小幫手'])

    required_cols = ['星期', '生物進度', '英文進度', '🎯考點提醒', '排課小幫手']
    if not all(col in plan_df.columns for col in required_cols):
        plan_df = pd.DataFrame([
            ["週一", "", "", "", ""],
            ["週二", "", "", "", ""],
            ["週三", "", "", "", ""],
            ["週四", "", "", "", ""],
            ["週五", "", "", "", ""]
        ], columns=required_cols)
        conn.update(worksheet="study_plan", data=plan_df)

    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    days = ["週一", "週二", "週三", "週四", "週五"]
    cols = st.columns(len(days))
    for i, day in enumerate(days):
        with cols[i]:
            st.markdown(f"<div style='text-align:center; font-weight:bold; color:#555;'>{day}</div>", unsafe_allow_html=True)
            day_data = plan_df[plan_df['星期'] == day]
            if not day_data.empty:
                row = day_data.iloc[0]
                st.markdown(f"<div class='slot-box bio'>🧬 {row['生物進度'] if row['生物進度'] else '待安排'}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='slot-box eng'>🌍 {row['英文進度'] if row['英文進度'] else '待安排'}</div>", unsafe_allow_html=True)
                if row['🎯考點提醒']:
                    st.markdown(f"<div class='point-tag'>🎯 {row['🎯考點提醒']}</div>", unsafe_allow_html=True)
                if row['排課小幫手']:
                    st.caption(f"✍️ 感謝 {row['排課小幫手']}")
            else:
                st.caption("休息")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("""<div class='collab-area'>""", unsafe_allow_html=True)
    st.subheader("📝 編輯區 (支援中文輸入)")
    
    new_plan = st.data_editor(
        plan_df, 
        use_container_width=True,
        column_config={
            "星期": st.column_config.SelectboxColumn("星期", options=["週一", "週二", "週三", "週四", "週五"], required=True),
            "生物進度": st.column_config.TextColumn("生物進度"),
            "英文進度": st.column_config.TextColumn("英文進度"),
            "🎯考點提醒": st.column_config.TextColumn("🎯考點提醒"),
            "排課小幫手": st.column_config.TextColumn("您的名字")
        }
    )
    
    if st.button("💾 提交建議課表", type="primary", use_container_width=True):
        with st.spinner("正在同步至雲端..."):
            conn.update(worksheet="study_plan", data=new_plan)
            st.balloons()
            st.toast("感謝你的排課建議！課表已更新。")
            time.sleep(1)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 5. 頁面：共同讀書區
# ==========================================
def joint_study_page():
    st.title("🏭 共同讀書區")
    st.caption("除了排課表，你也可以在這裡上傳具體的題目或筆記素材。")
    
    col_up, col_info = st.columns([1.2, 0.8])
    with col_up:
        name = st.text_input("貢獻者姓名", placeholder="您的名字")
        subj = st.selectbox("科目", ["生奧", "英文", "學測理化"])
        type_up = st.radio("上傳類型", ["題目/筆記素材", "🎯 考點建議"])
        note = st.text_area("內容描述 (支援中文輸入)")
        files = st.file_uploader("上傳圖片素材", accept_multiple_files=True)
        
        if st.button("🚀 確認送出", use_container_width=True):
            st.balloons()
            st.toast(f"感謝 {name}！您的貢獻已送達。")
    with col_info:
        st.markdown("### 📢 玩法說明")
        st.info("- **開放排課**：去「計畫展示」頁面幫我排課。\n- **提供素材**：在這裡上傳你覺得重要的考點。\n- **共同備考**：您的每一份建議都會出現在我的戰情室！")
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
