import streamlit as st
import pandas as pd
import base64
import time
import json
import re
import random
from io import BytesIO
from PIL import Image, ImageOps
from gtts import gTTS
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
import markdown

# ==========================================
# 1. 核心配置與視覺美化
# ==========================================
st.set_page_config(page_title="個人 AI 戰情室", page_icon="🚀", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            .hero-word { font-size: 2.8rem; font-weight: 800; color: #1A237E; }
            .vibe-box { background-color: #F0F7FF; padding: 20px; border-radius: 12px; border-left: 6px solid #2196F3; margin: 15px 0; }
            .breakdown-wrapper { background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%); padding: 25px 30px; border-radius: 15px; color: white !important; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 工具函式 (修正 LaTeX 重複問題)
# ==========================================
def get_gemini_keys():
    keys = st.secrets.get("GEMINI_FREE_KEYS", [])
    if isinstance(keys, str): keys = [keys]
    random.shuffle(keys)
    return keys

def fix_content(text):
    """修正換行與轉義問題"""
    if text is None or str(text).strip().lower() in ["無", "nan", ""]: return ""
    # 處理 JSON 轉義
    text = str(text).replace('\\\\', '\\').replace('\\n', '\n')
    # 轉為 Markdown 換行
    text = text.replace('\n', '  \n')
    return text.strip('"\' ')

def speak(text, key_suffix=""):
    english_only = re.sub(r"[^a-zA-Z0-9\s'-]", " ", str(text)).strip()
    if not english_only: return
    try:
        tts = gTTS(text=english_only, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        audio_base64 = base64.b64encode(fp.getvalue()).decode()
        uid = f"audio_{int(time.time()*1000)}_{key_suffix}"
        components.html(f'<button onclick="document.getElementById(\'{uid}\').play()">🔊 聽發音</button><audio id="{uid}" src="data:audio/mp3;base64,{audio_base64}"></audio>', height=40)
    except: pass

@st.cache_data(ttl=300)
def load_db():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl=0)
        return df.dropna(subset=['word']).fillna("無").reset_index(drop=True)
    except: return pd.DataFrame()

# ==========================================
# 3. 知識百科介面 (修正公式顯示)
# ==========================================
def show_encyclopedia_card(row):
    r_word = str(row.get('word', 'N/A'))
    
    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    
    # 1. 邏輯拆解
    st.markdown(f"<div class='breakdown-wrapper'><h4>🧬 邏輯拆解</h4>{fix_content(row.get('breakdown',''))}</div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🎯 定義")
        st.write(fix_content(row.get('definition','')))
        
    with c2:
        st.markdown("### 💡 核心原理")
        # 【去重關鍵】：先把所有錢字號拔掉，再包一組 $$，確保只渲染一次
        raw_roots = str(row.get('roots', '')).replace('$', '').strip()
        if raw_roots and raw_roots != "無":
            st.markdown(f"$${raw_roots}$$")
        else:
            st.write("（無原理資料）")
        st.write(f"**🔍 本質：** {row.get('meaning','')}")

    if row.get('native_vibe') != "無":
        st.markdown(f"<div class='vibe-box'><h4>🌊 專家心法</h4>{fix_content(row.get('native_vibe',''))}</div>", unsafe_allow_html=True)
    
    speak(r_word, f"card_{r_word}")

# ==========================================
# 4. 解碼實驗室 (預查 + 編輯後儲存)
# ==========================================
def ai_decode_only(input_text, category):
    keys = get_gemini_keys()
    if not keys: return None
    PROMPT = f"""Role: Polymath Decoder. JSON format only. Use \\\\n for newlines. Use \\\\LaTeX without $ for roots.
    Fields: category, word, roots, meaning, breakdown, definition, phonetic, native_vibe, memory_hook."""
    
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(f"{PROMPT}\n\nTarget: {input_text} in context of {category}")
            clean_json = re.sub(r'^```json\s*|\s*```$', '', res.text.strip(), flags=re.MULTILINE)
            return json.loads(clean_json)
        except: continue
    return None

def page_lab(df):
    st.title("🔬 解碼實驗室")
    
    col1, col2 = st.columns([2, 1])
    with col1: 
        target = st.text_input("輸入解碼主題", placeholder="例如：熵、貝氏定理...")
    with col2: 
        cat = st.selectbox("分類", ["物理科學", "英語辭源", "程式開發", "人工智慧", "自定義"])

    # --- 回覆預查功能 ---
    has_existing = False
    if target.strip():
        existing = df[df['word'].str.lower() == target.lower().strip()]
        if not existing.empty:
            has_existing = True
            st.warning(f"⚠️ 書架已有「{target}」。")
            with st.expander("查看現有內容"):
                show_encyclopedia_card(existing.iloc[0])
            re_decode = st.checkbox("我仍要重新解碼 (覆蓋舊資料)")
            if not re_decode: st.stop()

    if st.button("🚀 啟動 AI 解碼", type="primary"):
        with st.spinner("AI 解析中..."):
            draft = ai_decode_only(target, cat)
            if draft: st.session_state.temp_draft = draft
            else: st.error("AI 沒回應，請重試")

    # --- 草稿編輯區 ---
    if "temp_draft" in st.session_state:
        st.divider()
        st.subheader("📝 AI 草稿編輯區 (確認後再儲存)")
        d = st.session_state.temp_draft
        
        c_e1, c_e2 = st.columns(2)
        with c_e1:
            e_word = st.text_input("主題", d.get('word'))
            e_roots = st.text_input("原理 (LaTeX, 不要包$)", d.get('roots'))
        with c_e2:
            e_cat = st.text_input("分類", d.get('category'))
            e_meaning = st.text_input("本質意義", d.get('meaning'))

        e_breakdown = st.text_area("邏輯拆解", d.get('breakdown'), height=150)
        e_def = st.text_area("定義解釋", d.get('definition'), height=150)
        e_vibe = st.text_area("專家心法", d.get('native_vibe'), height=150)

        if st.button("✅ 確認無誤，寫入雲端書架", use_container_width=True):
            new_row = d.copy()
            new_row.update({"word": e_word, "roots": e_roots, "breakdown": e_breakdown, "definition": e_def, "native_vibe": e_vibe, "category": e_cat, "meaning": e_meaning})
            
            conn = st.connection("gsheets", type=GSheetsConnection)
            updated_df = pd.concat([df[df['word'] != e_word], pd.DataFrame([new_row])], ignore_index=True)
            conn.update(data=updated_df)
            
            st.success("儲存成功！")
            del st.session_state.temp_draft
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()

# ==========================================
# 5. 搜尋功能 (智慧模糊搜尋)
# ==========================================
def page_search(df):
    st.title("📖 知識庫搜尋")
    query = st.text_input("🔍 模糊搜尋 (多關鍵字請用空格分開)", placeholder="例如：物理 能量")
    
    if query:
        keywords = query.lower().split()
        # 只要資料列中包含所有輸入的關鍵字即符合
        mask = df.astype(str).apply(lambda x: all(k in x.str.lower().to_string() for k in keywords), axis=1)
        res = df[mask]
        
        if not res.empty:
            st.write(f"找到 {len(res)} 筆結果")
            for _, row in res.iterrows():
                with st.container(border=True): show_encyclopedia_card(row)
        else:
            st.warning("查無結果")
    else:
        st.dataframe(df[['word', 'category', 'definition']], use_container_width=True)

# ==========================================
# 6. 主程式
# ==========================================
def main():
    inject_custom_css()
    df = load_db()
    
    with st.sidebar:
        st.title("🚀 個人戰情室")
        mode = st.radio("功能切換", ["🔍 知識搜尋", "🔬 解碼實驗室", "🎓 講義排版大師"])
        st.divider()
        st.caption("v7.1 Efficient Edition")

    if mode == "🔍 知識搜尋": page_search(df)
    elif mode == "🔬 解碼實驗室": page_lab(df)
    elif mode == "🎓 講義排版大師":
        # 這裡調用你原有的 run_handout_app
        st.info("講義排版模組已開啟")
        # 建議將 generate_printable_html 的 MathJax 部分也依照 roots 去重邏輯檢查

if __name__ == "__main__":
    main()
