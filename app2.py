import streamlit as st
import pandas as pd
import json, re
from datetime import datetime, timedelta
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置 & 自動循環邏輯
# ==========================================
st.set_page_config(page_title="Kadowsella | 無限賽季版", page_icon="♾️", layout="wide")

SUBJECTS = ["國文", "英文", "數學A", "數學B", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

# --- [核心大腦] 動態計算目前的賽季資訊 ---
def get_cycle_info():
    """
    自動計算當前的「年度賽季」資訊。
    設定：每年 3 月 1 日為新賽季 (Week 1) 開始。
    學測日：鎖定為隔年 1 月 15 日。
    """
    now = datetime.now()
    current_year = now.year
    
    # 1. 判斷賽季起始日
    # 如果現在是 1月或 2月，賽季起始日應該是「去年」的 3/1
    if now.month < 3:
        cycle_start = datetime(current_year - 1, 3, 1)
    else:
        cycle_start = datetime(current_year, 3, 1)

    # 2. 判斷學測目標日
    # 這裡最關鍵：如果「今年的 1/15」已經過了，目標就必須是「明年的 1/15」
    exam_date = datetime(current_year, 1, 15)
    if now > exam_date:
        exam_date = datetime(current_year + 1, 1, 15)
        
    # 3. 計算閉關日 (考前 10 天)
    lockdown_date = exam_date - timedelta(days=10)
    
    # 4. 計算天數與週次
    days_to_exam = (exam_date - now).days
    
    delta_from_start = now - cycle_start
    current_week = (delta_from_start.days // 7) + 1
    
    # 防呆：防止出現負數週次
    if current_week < 1: current_week = 1
    
    return {
        "start_date": cycle_start,
        "exam_date": exam_date,
        "lockdown_date": lockdown_date,
        "week_num": current_week,
        "days_left": days_to_exam,
        "season_label": f"{cycle_start.year}-{exam_date.year} 賽季"
    }
# 取得全域賽季資訊
CYCLE = get_cycle_info()

def inject_custom_css():
    st.markdown("""
        <style>
            .hero-word { font-size: 2.5rem; font-weight: 800; color: #1E293B; }
            .subject-tag { background: #3B82F6; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
            .cycle-badge { 
                background: #0F172A; color: #38BDF8; padding: 5px 15px; 
                border-radius: 20px; font-size: 0.9rem; font-weight: bold; border: 1px solid #38BDF8;
                text-align: center; margin-bottom: 15px;
            }
            .peek-box {
                background: #F0F9FF; border: 1px dashed #0EA5E9; padding: 10px; 
                border-radius: 8px; margin-bottom: 8px; opacity: 0.8;
            }
            .peek-blur { filter: blur(4px); user-select: none; color: #94A3B8; }
            .stButton>button { border-radius: 8px; font-weight: bold; }
            #MainMenu {visibility: hidden;} footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 進度計算與資料庫
# ==========================================

def get_record_week(date_str):
    """計算某一筆資料是屬於該賽季的第幾週"""
    try:
        dt = datetime.strptime(str(date_str), "%Y-%m-%d")
        # 這裡要用當前賽季的開始日來算，才能對齊進度
        delta = dt - CYCLE["start_date"]
        # 如果是舊賽季的資料 (負數)，回傳 0 或負數
        return (delta.days // 7) + 1
    except: return 0

def is_in_lockdown():
    return datetime.now() >= CYCLE["lockdown_date"]

@st.cache_data(ttl=300)
def load_db(tick=0, admin_view=False):
    """
    admin_view=False 時，學生只能看到：
    1. 當前賽季的資料 (Current Season)
    2. 且週次 <= 目前週次 (No Spoilers)
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets.get("gsheets", {}).get("spreadsheet")
        if not url: return pd.DataFrame()
        
        df = conn.read(spreadsheet=url, ttl=0)
        if 'created_at' not in df.columns: 
            # 預設為本次賽季第一天，避免報錯
            df['created_at'] = CYCLE["start_date"].strftime("%Y-%m-%d")
        df = df.fillna("無")
        
        # 計算每筆資料的週次 (相對於本次賽季)
        df['week_num'] = df['created_at'].apply(get_record_week)
        
        if not admin_view:
            curr_w = CYCLE["week_num"]
            # 過濾掉未來的週次 (偷看保護)
            # 過濾掉上個賽季的資料 (若是你希望每年歸零)
            # 註：這裡設定 week_num > 0 代表只看本賽季。如果你想保留歷史庫存，可以拿掉 > 0 的限制。
            df = df[(df['week_num'] <= curr_w) & (df['week_num'] > 0)]
            
        return df
    except Exception as e:
        st.error(f"📡 {e}")
        return pd.DataFrame()

def save_to_db(new_data):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets["gsheets"]["spreadsheet"]
        existing_df = conn.read(spreadsheet=url, ttl=0)
        new_data['created_at'] = datetime.now().strftime("%Y-%m-%d")
        new_row = pd.DataFrame([new_data])
        updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        conn.update(spreadsheet=url, data=updated_df)
        st.toast(f"✅ 已寫入 {CYCLE['season_label']} (Week {CYCLE['week_num']})", icon="💾")
    except Exception as e:
        st.error(f"寫入失敗: {e}")

# ==========================================
# 3. AI & 顯示組件
# ==========================================
def ai_decode(input_text, subject):
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return None
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""請解析高中「{subject}」考點「{input_text}」。JSON: {{ "word": "{input_text}", "category": "{subject}", "roots": "核心公式/原理(LaTeX)", "breakdown": "拆解", "definition": "課綱定義", "native_vibe": "考試重點", "memory_hook": "口訣" }}"""
    try:
        res = model.generate_content(prompt)
        match = re.search(r'\{.*\}', res.text, re.DOTALL)
        if match: return json.loads(match.group(0))
    except: pass
    return None

def show_card(row, blur_content=False):
    if blur_content:
        st.markdown(f"""
        <div class="peek-box">
            <span class='subject-tag'>{row['category']}</span> <b>{row['word']}</b>
            <div style="margin-top:5px; font-size:0.8rem; color:#64748B;">🔒 Week {row['week_num']} 預告</div>
            <div class="peek-blur">內容封印中... 內容封印中...</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"<span class='subject-tag'>{row['category']}</span> <b>{row['word']}</b>", unsafe_allow_html=True)
        st.info(f"🧬 {row['breakdown']}")
        st.caption(f"💡 {row['definition']}")
        if str(row['roots']) != "無": st.success(f"📌 {row['roots']}")

# ==========================================
# 4. 主程式
# ==========================================
def main():
    inject_custom_css()
    if 'db_tick' not in st.session_state: st.session_state.db_tick = 0
    
    # 載入全部資料 (用於偷看邏輯)
    full_df = load_db(st.session_state.db_tick, admin_view=True)
    
    # 權限
    is_admin = False
    
    with st.sidebar:
        st.title("♾️ 永恆戰情室")
        
        # --- 賽季徽章 ---
        st.markdown(f"<div class='cycle-badge'>{CYCLE['season_label']}</div>", unsafe_allow_html=True)
        
        # 狀態
        days_left = (CYCLE["exam_date"] - datetime.now()).days
        if is_in_lockdown():
            st.error(f"🚨 考前閉關！ (剩 {days_left} 天)")
        else:
            st.info(f"📆 本季進度：第 {CYCLE['week_num']} 週\n\n🎯 距離學測：{days_left} 天")

        if st.button("🔄 同步狀態"):
            st.session_state.db_tick += 1
            st.cache_data.clear()
            st.rerun()

        # --- 水晶球偷看 ---
        with st.expander("🔮 偷看下週預告"):
            if st.button("👀 偷瞄一下"):
                next_w = CYCLE["week_num"] + 1
                if not full_df.empty:
                    # 篩選屬於本賽季 且 週次為下一週 的資料
                    # 這裡使用 get_record_week 動態算，確保不會撈到去年同週次的
                    full_df['dynamic_week'] = full_df['created_at'].apply(get_record_week)
                    preview_df = full_df[full_df['dynamic_week'] == next_w]
                    
                    if not preview_df.empty:
                        st.success(f"✨ 第 {next_w} 週 精彩預告：")
                        for _, row in preview_df.iterrows():
                            st.markdown(f"**[{row['category']}] {row['word']}**")
                    else:
                        st.warning(f"🐢 教官還沒把第 {next_w} 週的考點放進來喔！")

        with st.expander("🔑 教官登入"):
            if st.text_input("Pwd", type="password") == st.secrets.get("ADMIN_PASSWORD"):
                is_admin = True
                st.success("教官模式")

        menu = ["📅 本週訓練菜單", "🛡️ 本季知識庫存", "🎲 隨機驗收"]
        if is_admin: menu.append("🔬 預埋考點 (未來)")
        choice = st.radio("功能", menu)

    # 決定學生可見資料 (只看本賽季且已解鎖的)
    if is_admin:
        visible_df = full_df
    else:
        # 使用 apply 動態計算，確保換了年份後，舊資料不會變成「未來」
        if not full_df.empty:
            full_df['dynamic_week'] = full_df['created_at'].apply(get_record_week)
            # 篩選：大於0 (本賽季) 且 小於等於目前週次
            visible_df = full_df[(full_df['dynamic_week'] > 0) & (full_df['dynamic_week'] <= CYCLE["week_num"])]
        else:
            visible_df = pd.DataFrame()

    # ==========================
    # 1. 本週訓練
    # ==========================
    if choice == "📅 本週訓練菜單":
        st.title(f"📅 第 {CYCLE['week_num']} 週：本週任務")
        
        if is_in_lockdown():
            st.warning("🔒 閉關期不開放新進度！")
        else:
            if not visible_df.empty:
                # 再次確認只顯示當週
                this_week_df = visible_df[visible_df['dynamic_week'] == CYCLE['week_num']]
                
                if this_week_df.empty:
                    st.info("🍵 本週教官尚未發派新考點。")
                else:
                    st.success(f"🔥 本週新增 {len(this_week_df)} 個考點")
                    for _, row in this_week_df.iterrows():
                        with st.expander(f"📌 {row['category']} | {row['word']}", expanded=True):
                            show_card(row)
            else:
                st.info("尚無資料。")

    # ==========================
    # 2. 知識庫存
    # ==========================
    elif choice == "🛡️ 本季知識庫存":
        st.title("🛡️ 本季已解鎖庫存")
        
        if not visible_df.empty:
            # 找出本賽季之前的週次
            history_df = visible_df[visible_df['dynamic_week'] < CYCLE['week_num']]
            
            if history_df.empty:
                st.info("目前只有本週進度，尚無歷史庫存。")
            else:
                weeks = sorted(history_df['dynamic_week'].unique(), reverse=True)
                for w in weeks:
                    w_data = history_df[history_df['dynamic_week'] == w]
                    with st.expander(f"📂 第 {w} 週封存 ({len(w_data)} 考點)"):
                        for _, row in w_data.iterrows():
                            st.markdown("---")
                            show_card(row)
        else:
             st.warning("資料庫是空的。")

    # ==========================
    # 3. 隨機驗收
    # ==========================
    elif choice == "🎲 隨機驗收":
        st.title("🎲 隨機驗收 (本季範圍)")
        st.caption(f"📊 抽題池：共 {len(visible_df)} 題")
        
        if st.button("🎲 抽題", type="primary", use_container_width=True): st.rerun()
        
        if not visible_df.empty:
            row = visible_df.sample(1).iloc[0]
            st.markdown(f"**Week {row['dynamic_week']}**")
            show_card(row)

    # ==========================
    # 4. 預埋考點 (Admin)
    # ==========================
    elif choice == "🔬 預埋考點 (未來)" and is_admin:
        st.title(f"🔬 預埋考點 ({CYCLE['season_label']})")
        st.info(f"目前是第 {CYCLE['week_num']} 週。現在填入的資料會自動標記今天的日期。")
        
        c1, c2 = st.columns([3, 1])
        with c1: inp = st.text_input("輸入概念")
        with c2: sub = st.selectbox("科目", SUBJECTS)
        
        if st.button("生成並存入", type="primary"):
            res = ai_decode(inp, sub)
            if res:
                save_to_db(res)
                st.success("✅ 已寫入！")
                show_card(res)

if __name__ == "__main__":
    main()
