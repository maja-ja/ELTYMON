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
from PIL import Image

# ==========================================
# 0. 基礎配置與 CSS
# ==========================================
st.set_page_config(page_title="備考戰情展示櫃", page_icon="🛡️", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap');
            html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }
            
            /* 玻璃展示櫃樣式 */
            .glass-panel {
                background: rgba(255, 255, 255, 0.7);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                border: 1px solid rgba(255, 255, 255, 0.3);
                padding: 20px;
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
            }
            .grid-slot {
                background: white; border-left: 5px solid #FF4B4B;
                padding: 10px; margin-bottom: 10px; border-radius: 5px;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
            }
            .admin-only { border: 2px dashed #FF4B4B; padding: 15px; border-radius: 10px; background: #fff5f5; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 核心工具：權限與互動
# ==========================================
def check_auth():
    """檢查是否為本人（輸入密碼）"""
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    
    with st.sidebar:
        st.markdown("### 🔐 權限控制")
        if not st.session_state.is_admin:
            pwd = st.text_input("輸入管理員密碼", type="password")
            if st.button("解鎖編輯權限"):
                if pwd == st.secrets.get("ADMIN_PASSWORD", "1234"): # 預設1234
                    st.session_state.is_admin = True
                    st.success("🔓 已解鎖")
                    st.rerun()
                else:
                    st.error("密碼錯誤")
        else:
            if st.button("🔒 鎖定並退出"):
                st.session_state.is_admin = False
                st.rerun()
    return st.session_state.is_admin

def sidebar_interaction():
    """側邊欄加油與督促功能"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💬 社群互動")
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        # 讀取互動計數
        meta_df = conn.read(worksheet="meta_data", ttl=0)
    except:
        meta_df = pd.DataFrame([{"key": "cheers", "value": 0}, {"key": "pokes", "value": 0}])

    c1, c2 = st.sidebar.columns(2)
    
    if c1.button("🎈 送加油"):
        st.balloons()
        meta_df.loc[meta_df['key'] == 'cheers', 'value'] += 1
        conn.update(worksheet="meta_data", data=meta_df)
        st.sidebar.toast("收到你的加油了！感謝！")
        
    if c2.button("👉 督促讀書"):
        st.snow()
        meta_df.loc[meta_df['key'] == 'pokes', 'value'] += 1
        conn.update(worksheet="meta_data", data=meta_df)
        st.sidebar.toast("我會認真讀書的！別推了！")
    
    st.sidebar.info(f"✨ 累計加油：{int(meta_df[meta_df['key']=='cheers']['value'].iloc[0])} 次")

# ==========================================
# 2. AI 核心引擎 (多 Key 輪詢)
# ==========================================
def run_gemini_robust(prompt, images=None, model_name='gemini-2.5-flash'):
    keys = st.secrets.get("GEMINI_KEYS")
    if not keys:
        single_key = st.secrets.get("GEMINI_API_KEY")
        keys = [single_key] if single_key else []
    if not keys: return None
    if isinstance(keys, str): keys = [keys]
    
    shuffled_keys = list(keys).copy()
    random.shuffle(shuffled_keys)
    
    for api_key in shuffled_keys:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            content_parts = [prompt] + (images if images else [])
            response = model.generate_content(content_parts)
            if response and response.text: return response.text
        except: continue
    return None

# ==========================================
# 3. 模組：計畫展示櫃 (Scheduler Page)
# ==========================================
def scheduler_page():
    st.title("📅 讀書計畫展示櫃")
    is_admin = st.session_state.is_admin
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    try:
        plan_df = conn.read(worksheet="study_plan", ttl=0)
    except:
        plan_df = pd.DataFrame(columns=['day', 's1', 's2', 'status'])

    # --- 1. 展示展示區 (玻璃展示) ---
    st.markdown("### 🔍 本週公開進度")
    st.markdown("""<div class="glass-panel">""", unsafe_allow_html=True)
    cols = st.columns(5)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    
    for i, day in enumerate(days):
        with cols[i]:
            st.markdown(f"#### {day}")
            day_data = plan_df[plan_df['day'] == day]
            if not day_data.empty:
                st.markdown(f"<div class='grid-slot'>🧬 <b>{day_data.iloc[0]['s1']}</b></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='grid-slot' style='border-left-color:#007bff'>🌍 <b>{day_data.iloc[0]['s2']}</b></div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='color:#ccc'>暫無安排</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- 2. 管理區域 (上鎖) ---
    if is_admin:
        st.divider()
        st.subheader("⚙️ 課程編排 (管理員模式)")
        with st.form("admin_schedule"):
            edited_df = st.data_editor(plan_df, num_rows="dynamic", use_container_width=True)
            if st.form_submit_button("💾 鎖定並發佈新課表"):
                conn.update(worksheet="study_plan", data=edited_df)
                st.success("課表已同步至展示櫃！")
                st.rerun()
    else:
        st.info("🔒 計畫表目前為「唯讀狀態」。若要重新編排，請於側邊欄輸入密碼。")

# ==========================================
# 4. 模組：開放命題工廠 (Exam Factory)
# ==========================================
def factory_page():
    st.title("🏭 開放命題工廠")
    st.caption("任何人都可以幫助我備考！上傳你的資料，AI 會幫我出一題。")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 1. 提交資料")
        contributor = st.text_input("你的名字/暱稱", placeholder="匿名好友")
        subj = st.selectbox("科目", ["生奧", "托福/多益", "學測/自然", "其他"])
        context = st.text_area("參考文字或概念", placeholder="可以貼上一段文章或筆記...")
        uploaded_files = st.file_uploader("上傳參考圖片", type=["jpg", "png"], accept_multiple_files=True)
        
        if st.button("🚀 生成題目並送出", type="primary"):
            with st.spinner("AI 正在解析並命題中..."):
                prompt = f"你是專業命題官，請針對「{subj}」出的題目。格式: JSON {{'q':'','options':['A.','B.','C.','D.'],'answer':'A','explanation':''}}"
                imgs = [Image.open(f) for f in uploaded_files] if uploaded_files else []
                raw_res = run_gemini_robust(prompt + f"\n參考文字: {context}", images=imgs)
                
                if raw_res:
                    try:
                        clean_json = re.sub(r"```json|```", "", raw_res).strip()
                        q_data = json.loads(clean_json)
                        # 直接入庫
                        conn = st.connection("gsheets", type=GSheetsConnection)
                        bank_df = conn.read(worksheet="quiz_bank", ttl=0)
                        new_row = {
                            "id": str(uuid.uuid4())[:8],
                            "date": datetime.date.today().strftime("%Y-%m-%d"),
                            "subject": subj,
                            "topic": f"來自 {contributor}",
                            "question_json": json.dumps(q_data, ensure_ascii=False),
                            "user_answer": "", "is_correct": "Pending"
                        }
                        updated_df = pd.concat([bank_df, pd.DataFrame([new_row])], ignore_index=True)
                        conn.update(worksheet="quiz_bank", data=updated_df)
                        st.balloons()
                        st.success(f"感謝 {contributor}！這題已經進入我的挑戰區。")
                    except: st.error("AI 生成出錯，請再試一次。")

    with col2:
        st.markdown("### ✨ 如何參與？")
        st.info("""
        1. **提供素材**：你可以貼上你覺得很難的觀念或圖片。
        2. **AI 轉化**：系統會自動根據素材出一題單選題。
        3. **遠端挑戰**：題目會被存入我的「挑戰區」，我有空就會去刷題！
        """)
        st.image("https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJndmthZzR3eHBybmZ4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/l0HlBO7eyXzSZkJri/giphy.gif", use_column_width=True)

# ==========================================
# 5. 模組：競技場與已寫題區 (Arena)
# ==========================================
def arena_page():
    st.title("⚔️ 挑戰競技場")
    is_admin = st.session_state.is_admin
    
    tab1, tab2 = st.tabs(["🔥 挑戰進行中", "🏆 榮譽殿堂 (已完成)"])
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        bank_df = conn.read(worksheet="quiz_bank", ttl=0)
    except:
        st.warning("資料庫讀取中...")
        return

    with tab1:
        pending_df = bank_df[bank_df['is_correct'] == "Pending"]
        if pending_df.empty:
            st.success("🎉 目前題庫空空如也！去命題工廠加料吧。")
        else:
            if not is_admin:
                st.warning("🔒 刷題區僅限本人登入操作，訪客請點選「榮譽殿堂」觀看。")
                st.write(f"目前還有 {len(pending_df)} 題等待被解決。")
            else:
                st.subheader(f"還剩下 {len(pending_df)} 題，加油！")
                # (此處保留原有的刷題邏輯...)
                row = pending_df.iloc[0]
                q_data = json.loads(row['question_json'])
                st.markdown(f"<div class='quiz-card'>{q_data['q']}</div>", unsafe_allow_html=True)
                ans = st.radio("你的選擇：", q_data['options'], index=None)
                if st.button("提交答案"):
                    # 更新邏輯...
                    st.rerun()

    with tab2:
        st.subheader("📜 已寫題目觀賞區")
        st.caption("這是我的讀書足跡，歡迎隨意翻閱。")
        done_df = bank_df[bank_df['is_correct'] != "Pending"].sort_values(by="date", ascending=False)
        
        for i, row in done_df.iterrows():
            q = json.loads(row['question_json'])
            status = "✅ 正確" if row['is_correct'] == "TRUE" else "❌ 錯誤"
            with st.expander(f"{row['date']} | {row['subject']} | {status}"):
                st.markdown(f"**題目：** {q['q']}")
                st.markdown(f"**你的答案：** `{row['user_answer']}` | **正解：** `{q['answer']}`")
                st.markdown(f"**💡 解析：** {q['explanation']}")

# ==========================================
# 6. 主程式導航
# ==========================================
def main():
    inject_custom_css()
    is_admin = check_auth()
    sidebar_interaction()
    
    page = st.sidebar.selectbox("切換區域", ["首頁儀表板", "計畫展示櫃", "命題工廠 (開放)", "競技場 (展示/刷題)"])
    
    if page == "首頁儀表板":
        st.title("🛡️ 備考戰情室展示中心")
        st.markdown("這裡是我備考的實況台，你可以透過上方選項查看我的課表或幫我出題。")
        # 顯示倒數計時與數據
        targets = [{"name": "生物奧林匹亞", "date": "2026-11-01"}, {"name": "學測", "date": "2027-01-20"}]
        cols = st.columns(len(targets))
        for i, t in enumerate(targets):
            days = (datetime.datetime.strptime(t['date'], "%Y-%m-%d").date() - datetime.date.today()).days
            cols[i].metric(t['name'], f"{days} 天", t['date'])
            
    elif page == "計畫展示櫃":
        scheduler_page()
    elif page == "命題工廠 (開放)":
        factory_page()
    elif page == "競技場 (展示/刷題)":
        arena_page()

if __name__ == "__main__":
    main()
