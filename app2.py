import streamlit as st
import pandas as pd
import json, re
from datetime import datetime, timedelta
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 核心配置 & 無限循環大腦
# ==========================================
st.set_page_config(page_title="Kadowsella | 無限賽季版", page_icon="♾️", layout="wide")

SUBJECTS = ["國文", "英文", "數學A", "數學B", "物理", "化學", "生物", "地科", "歷史", "地理", "公民"]

def get_cycle_info():
    """
    自動計算當前的「年度賽季」資訊。
    開訓日：每年 3 月 1 日 (Week 1)
    學測日：每年 1 月 15 日
    """
    now = datetime.now()
    current_year = now.year
    
    # 判斷賽季起始日：1-2月算去年的循環，3月後算今年的
    if now.month < 3:
        cycle_start = datetime(current_year - 1, 3, 1)
    else:
        cycle_start = datetime(current_year, 3, 1)

    # 判斷學測目標日：如果今年的 1/15 過了，目標就是明年的 1/15
    exam_date = datetime(current_year, 1, 15)
    if now > exam_date:
        exam_date = datetime(current_year + 1, 1, 15)
        
    lockdown_date = exam_date - timedelta(days=10)
    days_left = (exam_date - now).days
    
    # 計算週次
    delta_from_start = now - cycle_start
    current_week = (delta_from_start.days // 7) + 1
    if current_week < 1: current_week = 1
    
    return {
        "start_date": cycle_start,
        "exam_date": exam_date,
        "lockdown_date": lockdown_date,
        "week_num": current_week,
        "days_left": days_left,
        "season_label": f"{cycle_start.year}-{exam_date.year} 賽季"
    }

CYCLE = get_cycle_info()
def ai_decode(input_text, subject):
    """
    管理員專用：呼叫 Gemini 1.5 Flash 進行知識解構。
    自動適應最新的 108 課綱脈絡。
    """
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("❌ 找不到 GEMINI_API_KEY，請在 Secrets 中設定。")
        return None

    # 配置 Google Gemini API
    genai.configure(api_key=api_key)
    
    # 這裡使用的是動態更新模型，Google 會自動升級其後台邏輯
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 針對台灣升學考試優化的系統提示詞
    system_instruction = f"""
    你現在是台灣高中升學考試（學測/分科測驗）的頂尖名師，目標是帶領學生考上台大醫學系。
    請針對「{subject}」科目中的概念「{input_text}」進行深度解析。
    
    請嚴格遵守以下欄位邏輯並輸出 JSON 格式：
    1. roots: 若理科則提供 LaTeX 核心公式；若文科則提供字源或核心邏輯。
    2. definition: 108 課綱標準定義，要精準、專業。
    3. breakdown: 條列式重點拆解，使用 \\n 換行。
    4. memory_hook: 創意口訣、諧音或聯想圖像。
    5. native_vibe: 考試陷阱、常考題型或重要程度提醒。
    
    輸出格式要求：
    - 必須是純 JSON，不要包含 Markdown 的 ```json 標記。
    - 所有的 Key 必須為：word, category, roots, breakdown, definition, native_vibe, memory_hook。
    - 內容中的引號請使用中文「」或單引號 '，避免破壞 JSON 結構。
    """
    
    try:
        response = model.generate_content(system_instruction)
        
        # 提取 JSON 的正則表達式，增加穩定性
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
            
            # 強制校正基本欄位，確保資料一致性
            data['word'] = input_text
            data['category'] = subject
            
            # 補足可能缺失的欄位，防止存檔報錯
            defaults = ["meaning", "phonetic", "example", "translation"]
            for field in defaults:
                if field not in data:
                    data[field] = "無"
                    
            return data
        else:
            st.error("AI 回傳格式有誤，請重試一次。")
            return None
            
    except Exception as e:
        st.error(f"AI 運算發生錯誤: {e}")
        return None
def inject_custom_css():
    st.markdown("""
        <style>
            .breakdown-wrapper { 
                background: #F8FAFC; 
                color: #1E293B !important; /* 強制使用深色字，避免在黑魂模式下變白色 */
                padding: 20px; 
                border-radius: 12px; 
                border-left: 5px solid #3B82F6; 
                line-height: 1.6;
            }
            /* 讓定義區的文字也清晰可見 */
            .stInfo, .stSuccess, .stWarning {
                color: #1E293B !important;
            }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 資料庫邏輯
# ==========================================

@st.cache_data(ttl=300)
def load_db(tick=0):
    try:
        # 建立連線，它會自動讀取 [connections.gsheets] 區塊的所有 secrets
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # 讀取資料：不需要再次傳入 URL，只要 Secrets 裡有 spreadsheet 欄位即可
        df = conn.read(ttl=0)
        
        if 'created_at' not in df.columns:
            df['created_at'] = "2026-03-01"
            
        return df.fillna("無")
    except Exception as e:
        st.error(f"📡 資料庫讀取失敗: {e}")
        return pd.DataFrame()

def save_to_db(new_data):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # 1. 先讀取現有資料
        existing_df = conn.read(ttl=0)
        
        # 2. 準備新資料
        new_data['created_at'] = datetime.now().strftime("%Y-%m-%d")
        new_row = pd.DataFrame([new_data])
        
        # 3. 合併
        updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        
        # 4. 寫入 (此時 conn 已經具備 Service Account 權限)
        conn.update(data=updated_df)
        
        st.toast(f"✅ 成功洗入資料庫！", icon="💾")
    except Exception as e:
        # 如果還是報錯 Spreadsheet must be specified，代表 Secrets 結構有誤
        st.error(f"❌ 寫入失敗：{e}")

# ==========================================
# 3. 顯示與輔助功能
# ==========================================

def get_record_week(date_str):
    try:
        dt = datetime.strptime(str(date_str), "%Y-%m-%d")
        delta = dt - CYCLE["start_date"]
        return (delta.days // 7) + 1
    except: return 0

def show_card(row):
    st.markdown(f"<span class='subject-tag'>{row['category']}</span> <b>{row['word']}</b>", unsafe_allow_html=True)
    st.markdown(f"<div class='breakdown-wrapper'>🧬 {row['breakdown']}</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.info(f"💡 {row['definition']}")
    with c2: st.success(f"📌 {row['roots']}")

# ==========================================
# 4. 主程式頁面
# ==========================================

def main():
    inject_custom_css()
    if 'db_tick' not in st.session_state: st.session_state.db_tick = 0
    full_df = load_db(st.session_state.db_tick)
    
    is_admin = False
    with st.sidebar:
        st.title("♾️ 永恆戰情室")
        st.markdown(f"<div class='cycle-badge'>{CYCLE['season_label']}</div>", unsafe_allow_html=True)
        
        # 狀態顯示邏輯
        days_left = CYCLE["days_left"]
        if days_left > 330:
            st.success("🍃 賽季交替期：2026 戰役結束")
            st.write(f"距離 2027 學測剩 {days_left} 天")
        elif datetime.now() >= CYCLE["lockdown_date"]:
            st.error(f"🚨 考前 10 天閉關！ (剩 {days_left} 天)")
        else:
            st.info(f"📆 本季進度：第 {CYCLE['week_num']} 週\n\n🎯 距離學測：{days_left} 天")

        if st.button("🔄 同步雲端"):
            st.session_state.db_tick += 1
            st.cache_data.clear()
            st.rerun()

        # 🔮 偷看功能
        with st.expander("🔮 偷看下週預告"):
            if st.button("👀 偷瞄"):
                next_w = CYCLE["week_num"] + 1
                if not full_df.empty:
                    full_df['dynamic_week'] = full_df['created_at'].apply(get_record_week)
                    p_df = full_df[full_df['dynamic_week'] == next_w]
                    if not p_df.empty:
                        for _, r in p_df.iterrows(): st.write(f"· [{r['category']}] {r['word']}")
                    else: st.write("尚無預告。")

        with st.expander("🔑 管理員"):
            if st.text_input("Pwd", type="password") == st.secrets.get("ADMIN_PASSWORD"):
                is_admin = True
        
        menu = ["📅 本週訓練菜單", "🛡️ 歷史考點回顧", "🎲 隨機抽題"]
        if is_admin: menu.append("🔬 預埋考點")
        choice = st.radio("功能", menu)

    # 資料分流
    if not full_df.empty:
        full_df['dynamic_week'] = full_df['created_at'].apply(get_record_week)
        # 學生只能看到當前賽季且已解鎖的
        if is_admin: visible_df = full_df
        else: visible_df = full_df[(full_df['dynamic_week'] > 0) & (full_df['dynamic_week'] <= CYCLE["week_num"])]
    else: visible_df = pd.DataFrame()

    if choice == "📅 本週訓練菜單":
        st.title(f"📅 第 {CYCLE['week_num']} 週任務")
        if not visible_df.empty:
            this_week = visible_df[visible_df['dynamic_week'] == CYCLE['week_num']]
            if this_week.empty: st.info("本週尚無新考點。")
            else:
                for _, r in this_week.iterrows():
                    with st.expander(f"📌 {r['word']}", expanded=True): show_card(r)
        else: st.info("等待開訓...")

    elif choice == "🛡️ 歷史考點回顧":
        st.title("🛡️ 知識庫存")
        if not visible_df.empty:
            hist = visible_df[visible_df['dynamic_week'] < CYCLE['week_num']]
            weeks = sorted(hist['dynamic_week'].unique(), reverse=True)
            for w in weeks:
                with st.expander(f"📂 第 {w} 週回顧"):
                    for _, r in hist[hist['dynamic_week'] == w].iterrows():
                        st.markdown("---")
                        show_card(r)

    elif choice == "🎲 隨機抽題":
        st.title("🎲 隨機驗收")
        if st.button("🎲 抽題"): st.rerun()
        if not visible_df.empty:
            row = visible_df.sample(1).iloc[0]
            st.caption(f"來自 Week {row['dynamic_week']}")
            show_card(row)

    elif choice == "🔬 預埋考點" and is_admin:
        st.title("🔬 AI 考點填裝 (上帝模式)")
        st.info(f"當前賽季：{CYCLE['season_label']} | 預計寫入：Week {CYCLE['week_num']}")
        
        c1, c2 = st.columns([3, 1])
        with c1:
            inp = st.text_input("輸入要拆解的學科概念", placeholder="例如：赫茲實驗、木蘭詩、邊際效用...")
        with c2:
            sub = st.selectbox("所屬科目", SUBJECTS)
        
        if st.button("🚀 啟動 AI 解碼並存入", type="primary", use_container_width=True):
            if not inp:
                st.warning("請輸入內容才能解碼！")
            else:
                with st.spinner(f"正在以【{sub}】名師視角進行深度拆解..."):
                    # 1. 執行 AI 解碼
                    res_data = ai_decode(inp, sub)
                    
                    if res_data:
                        # 2. 顯示即時預覽
                        st.subheader("👀 生成預覽")
                        show_card(res_data)
                        
                        # 3. 寫入 Google Sheets
                        save_to_db(res_data)
                        
                        # 4. 成功回饋
                        st.balloons()
                        st.success(f"🎉 成功！「{inp}」已洗入 {CYCLE['season_label']} 的資料庫。")
                    else:
                        st.error("AI 解碼失敗，請檢查 API Key 或網路連線。")
if __name__ == "__main__":
    main()
