import base64
import datetime
import io
import math
import os
import pandas as pd
from PIL import Image
import streamlit as st

# 設定網頁基本排版
st.set_page_config(page_title="身態模擬器", page_icon="🎮", layout="wide")

# 自訂高對比美化樣式與卡片設計
st.markdown(
    """
    <style>
    .main { background-color: var(--background-color); }
    .stMetric {
        background-color: var(--secondary-background-color);
        padding: 12px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    h1, h2, h3, h4, h5, h6, p, span, label, div {
        color: var(--text-color) !important;
    }
    .rpg-card {
        background: var(--secondary-background-color);
        border: 2px solid #ff4b4b;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 8px 16px rgba(0,0,0,0.15);
        text-align: center;
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    .goal-card {
        background: var(--secondary-background-color);
        border-radius: 16px;
        padding: 18px;
        margin-top: 12px;
        border: 1px solid rgba(255,75,75,0.35);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 初始化暫存記憶體
if "history" not in st.session_state:
    st.session_state.history = []
if "water_history" not in st.session_state:
    st.session_state.water_history = []
if "water" not in st.session_state:
    st.session_state.water = 0
if "last_feedback" not in st.session_state:
    st.session_state.last_feedback = (
        "🎮 歡迎進入身態模擬器！請設定你的基本資料並開始記錄健康生活吧！"
    )

st.title("🌱 身態模擬器")

# ==================== 固定體態 PNG + 漸進式 GIF 對應 ====================
BODY_IMAGE_FILES = {
    "女": {
        0: "female_very_thin.png",
        1: "female_thin.png",
        2: "female_normal.png",
        3: "female_overweight.png",
        4: "female_obese.png",
    },
    "男": {
        0: "male_very_thin.png",
        1: "male_thin.png",
        2: "male_normal.png",
        3: "male_overweight.png",
        4: "male_obese.png",
    },
}


def get_progression_gif_path(gender):
    filename = (
        "female_body_progression.gif"
        if gender == "女"
        else "male_body_progression.gif"
    )
    path = os.path.join("images", filename)
    return path if os.path.exists(path) else None


def get_character_image_path(gender, tier_idx):
    gender_map = BODY_IMAGE_FILES.get(gender, BODY_IMAGE_FILES["女"])
    filename = gender_map.get(int(tier_idx), gender_map[2])
    path = os.path.join("images", filename)
    return path if os.path.exists(path) else None


# 移除快取裝飾器，確保剛上傳的圖片能即時讀取
def get_character_avatar_base64(gender, tier_idx):
    image_path = get_character_image_path(gender, tier_idx)
    if not image_path:
        return ""
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        img_str = base64.b64encode(image_bytes).decode()
        return f"data:image/png;base64,{img_str}"
    except Exception:
        return ""


def get_body_progression_gif(gender):
    return get_progression_gif_path(gender)


# ==================== 食物資料庫 ====================
ORIGINAL_FOOD_DB = [
    {"name": "三明治 (Sandwich, 1份)", "cal": 320.0, "pro": 12.0, "carb": 35.0, "fat": 14.0},
    {"name": "蛋餅 (Dan Bing, 1份)", "cal": 300.0, "pro": 10.0, "carb": 35.0, "fat": 12.0},
    {"name": "飯糰 (Taiwanese Rice Ball, 1顆)", "cal": 420.0, "pro": 12.0, "carb": 58.0, "fat": 15.0},
    {"name": "滷肉飯 (Braised Pork Rice, 1碗)", "cal": 500.0, "pro": 15.0, "carb": 65.0, "fat": 20.0},
    {"name": "雞排 (Fried Chicken Cutlet, 1份)", "cal": 650.0, "pro": 35.0, "carb": 40.0, "fat": 42.0},
    {"name": "牛肉麵 (Beef Noodle Soup, 1碗)", "cal": 600.0, "pro": 28.0, "carb": 70.0, "fat": 22.0},
    {"name": "白米飯 (White Rice, 1碗)", "cal": 280.0, "pro": 5.4, "carb": 61.0, "fat": 0.6},
    {"name": "水煮雞胸肉 (Chicken Breast, 100g)", "cal": 165.0, "pro": 31.0, "carb": 0.0, "fat": 3.6},
    {"name": "珍珠奶茶 (Bubble Tea, 700ml/微糖)", "cal": 450.0, "pro": 4.0, "carb": 75.0, "fat": 15.0},
    {"name": "美式咖啡 (Black Coffee, 360ml)", "cal": 15.0, "pro": 1.0, "carb": 2.0, "fat": 0.0},
]


def load_food_database():
    csv_path = os.path.join("food_database.csv")
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            required = {"name", "cal", "pro", "carb", "fat"}
            if required.issubset(df.columns):
                df = df.fillna("")
                return df.to_dict("records")
        except Exception:
            pass
    return ORIGINAL_FOOD_DB


TAIWAN_FOOD_DB = load_food_database()


def search_foods(keyword):
    if not keyword:
        return TAIWAN_FOOD_DB[:80]
    keyword_lower = keyword.strip().lower()
    results = [
        food for food in TAIWAN_FOOD_DB
        if keyword_lower in str(food["name"]).lower()
    ]
    if not results:
        results = [{
            "name": f"✨ AI 智慧推估食物：{keyword} (1份)",
            "cal": 400.0,
            "pro": 15.0,
            "carb": 45.0,
            "fat": 18.0,
        }]
    return results[:80]


# ==================== 版面配置 ====================
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.markdown("### 📋 基本資料")
    char_name = st.text_input("角色名稱", value="小勇士")
    col_s1, col_s2 = st.columns(2)

    with col_s1:
        age = st.number_input("年齡 (歲)", min_value=1, max_value=120, value=25)
        height = st.number_input("身高 (cm)", min_value=50.0, max_value=230.0, value=150.0)
        target_weight = st.number_input("目標體重 (kg)", min_value=20.0, max_value=250.0, value=45.0)
        target_weeks = st.number_input("目標期限 (週)", min_value=1, max_value=520, value=12, step=1)

    with col_s2:
        gender = st.selectbox("性別", ["女", "男"])
        weight = st.number_input("目前體重 (kg)", min_value=20.0, max_value=250.0, value=50.0)

# 數值計算
if gender == "女":
    bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
else:
    bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5

tdee = bmr * 1.2
bmi = weight / ((height / 100) ** 2)
recommended_water = max(1500, weight * 35 + (height - 150) * 3)


def get_body_tier(b):
    if b < 17.0:
        return 0, "很瘦 (過輕)"
    elif 17.0 <= b < 18.5:
        return 1, "瘦 (偏瘦)"
    elif 18.5 <= b < 24.0:
        return 2, "正常 (健康)"
    elif 24.0 <= b < 27.0:
        return 3, "微胖 (過重)"
    else:
        return 4, "很胖 (肥胖)"


tier_idx, body_state = get_body_tier(bmi)
current_avatar_url = get_character_avatar_base64(gender, tier_idx)

with col_right:
    st.markdown(
        f"""
        <div class="rpg-card">
            <img src="{current_avatar_url}" width="300"
                 style="object-fit:contain; height:360px; border-radius:12px;
                        background:rgba(255,255,255,0.05); margin-bottom:10px;">
            <h2 style="margin:0; color:#ff4b4b;">{char_name}</h2>
            <p style="margin:5px 0 0 0; font-weight:bold; font-size:20px;">
                狀態：{body_state}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# 分頁架構
tab1, tab2, tab3 = st.tabs(["🍱 三餐紀錄", "💧 水分與日常追蹤", "🤖 今天這樣吃好嗎"])


def render_food_selector_section(unique_key_prefix):
    search_keyword = st.text_input("輸入關鍵字搜尋", "", key=f"{unique_key_prefix}_kw")
    matched_foods = search_foods(search_keyword)
    options = [f["name"] for f in matched_foods]
    options.append("✏️ 自訂食物與營養素 (手動輸入)")

    sel_key = f"{unique_key_prefix}_sel"
    prev_sel_key = f"{unique_key_prefix}_prev_sel"

    selected_option = st.selectbox("選擇搜尋結果", options, key=sel_key)

    if selected_option == "✏️ 自訂食物與營養素 (手動輸入)":
        default_cal, default_pro, default_carb, default_fat = 350.0, 15.0, 40.0, 12.0
    else:
        matched_item = next((f for f in matched_foods if f["name"] == selected_option), matched_foods[0])
        default_cal = matched_item["cal"]
        default_pro = matched_item["pro"]
        default_carb = matched_item["carb"]
        default_fat = matched_item["fat"]

    if prev_sel_key not in st.session_state or st.session_state[prev_sel_key] != selected_option:
        st.session_state[f"{unique_key_prefix}_fcal"] = float(default_cal)
        st.session_state[f"{unique_key_prefix}_fpro"] = float(default_pro)
        st.session_state[f"{unique_key_prefix}_fcarb"] = float(default_carb)
        st.session_state[f"{unique_key_prefix}_ffat"] = float(default_fat)
        st.session_state[prev_sel_key] = selected_option
        st.rerun()

    c1, c2, c3, c4 = st.columns(4)
    f_cal = c1.number_input("熱量 (kcal)", key=f"{unique_key_prefix}_fcal", min_value=0.0)
    f_pro = c2.number_input("蛋白質 (g)", key=f"{unique_key_prefix}_fpro", min_value=0.0)
    f_carb = c3.number_input("碳水 (g)", key=f"{unique_key_prefix}_fcarb", min_value=0.0)
    f_fat = c4.number_input("脂肪 (g)", key=f"{unique_key_prefix}_ffat", min_value=0.0)

    return selected_option, f_cal, f_pro, f_carb, f_fat


# 分頁一：三餐紀錄
with tab1:
    st.subheader("📝 三餐與營養素記錄")
    meal_category = st.selectbox("選擇餐別", ["早餐", "午餐", "晚餐", "宵夜"])
    food_name, food_cal, food_pro, food_carb, food_fat = render_food_selector_section("tab1")

    if st.button("➕ 確認新增紀錄", type="primary"):
        st.session_state.history.append({
            "date": str(datetime.date.today()),
            "meal": meal_category,
            "food": food_name,
            "cal": food_cal,
            "pro": food_pro,
            "carb": food_carb,
            "fat": food_fat,
        })
        st.success(f"成功記錄！『{char_name}』的冒險日誌已更新。")
        st.rerun()

    if st.session_state.history:
        st.write("### 📋 今日飲食清單")
        st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True)


# 分頁二：水分與日常追蹤
with tab2:
    st.subheader("💧 每日水分攝取量追蹤")
    st.info(f"💡 每日建議飲水量為：**{recommended_water:.0f} c.c.**")
    st.write(f"目前已補充水分：**{st.session_state.water} c.c.** / 目標 **{recommended_water:.0f} c.c.**")

    col_w1, col_w2, col_w3 = st.columns(3)
    if col_w1.button("💧 喝一杯水 (+250 c.c.)"):
        st.session_state.water += 250
        st.session_state.water_history.append({"date": str(datetime.date.today()), "action": "喝一杯水", "amount": "250 c.c.", "total_water": f"{st.session_state.water} c.c."})
        st.success("成功記錄 250 c.c. 水分！")
        st.rerun()

    if col_w2.button("🚰 大口灌水 (+500 c.c.)"):
        st.session_state.water += 500
        st.session_state.water_history.append({"date": str(datetime.date.today()), "action": "大口灌水", "amount": "500 c.c.", "total_water": f"{st.session_state.water} c.c."})
        st.success("成功記錄 500 c.c. 水分！")
        st.rerun()

    if col_w3.button("🔄 重置水分歸零"):
        st.session_state.water = 0
        st.session_state.water_history = []
        st.success("水分紀錄已重置歸零！")
        st.rerun()

    st.write("### 📋 飲水紀錄")
    if st.session_state.water_history:
        st.dataframe(pd.DataFrame(st.session_state.water_history), use_container_width=True)
    else:
        st.info("目前尚無飲水紀錄。")


# 分頁三：今天這樣吃好嗎 (包含點擊後才會連動顯示的 Before/After 與漸進動畫)
with tab3:
    st.subheader("🤖 今天這樣吃好嗎")
    st.info("💡 選擇三餐，設定模擬天數，點擊下方按鈕即可一鍵連動檢視長期體態轉變！")

    st.markdown("---")
    st.markdown("#### 🍳 早餐")
    bf_name, bf_cal, bf_pro, bf_carb, bf_fat = render_food_selector_section("tab4_breakfast")

    st.markdown("---")
    st.markdown("#### 🍱 午餐")
    lu_name, lu_cal, lu_pro, lu_carb, lu_fat = render_food_selector_section("tab4_lunch")

    st.markdown("---")
    st.markdown("#### 🍲 晚餐")
    di_name, di_cal, di_pro, di_carb, di_fat = render_food_selector_section("tab4_dinner")

    total_day_cal = bf_cal + lu_cal + di_cal
    total_day_pro = bf_pro + lu_pro + di_pro
    total_day_carb = bf_carb + lu_carb + di_carb
    total_day_fat = bf_fat + lu_fat + di_fat

    st.markdown("---")
    st.markdown("#### 📊 全天總計與模擬設定")
    c_t1, c_t2, c_t3, c_t4 = st.columns(4)
    c_t1.metric("總熱量", f"{total_day_cal:.0f} kcal")
    c_t2.metric("總蛋白質", f"{total_day_pro:.1f} g")
    c_t3.metric("總碳水", f"{total_day_carb:.1f} g")
    c_t4.metric("總脂肪", f"{total_day_fat:.1f} g")

    sim_days = st.slider(
        "如果連續維持此飲食，想模擬未來幾天的變化？",
        min_value=7,
        max_value=180,
        value=30,
        step=7,
    )

    simulated_daily_balance = total_day_cal - tdee
    simulated_weight_long = weight + (simulated_daily_balance * sim_days / 7700)
    simulated_weight_long = max(20.0, simulated_weight_long)
    simulated_bmi_long = simulated_weight_long / ((height / 100) ** 2)

    s1, s2, s3 = st.columns(3)
    s1.metric("每日熱量差", f"{simulated_daily_balance:+.0f} kcal")
    s2.metric(f"{sim_days} 天後估算體重", f"{simulated_weight_long:.1f} kg")
    s3.metric("估算 BMI", f"{simulated_bmi_long:.1f}")

    # 點擊模擬按鈕後，才會連動顯示：Before vs After 圖片與漸進式 GIF 動畫
    if st.button("🚀 啟動模擬分析與漸進變化", type="primary"):
        st.write("---")
        st.markdown(f"### 🛡️ 【{char_name}】的 {sim_days} 天體態轉變模擬")

        simulated_tier, simulated_body_state = get_body_tier(simulated_bmi_long)
        if total_day_cal - tdee > 0:
            simulated_body_state += " (⚠️ 熱量超載警戒)"

        simulated_avatar_url = get_character_avatar_base64(gender, simulated_tier)

        # 1. 顯示 Before 與 After 對比卡片
        col_img1, col_img2 = st.columns(2)
        with col_img1:
            st.markdown(
                f"""
                <div style="background:var(--secondary-background-color); padding:15px; border-radius:12px; text-align:center; border:2px solid #3498db;">
                    <p style="font-weight:bold; font-size:16px; margin-bottom:8px;">Before (目前)</p>
                    <img src="{current_avatar_url}" width="200" style="object-fit:contain; height:220px; margin-bottom:8px;">
                    <p style="margin:0; font-size:14px; font-weight:bold;">{body_state}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_img2:
            st.markdown(
                f"""
                <div style="background:var(--secondary-background-color); padding:15px; border-radius:12px; text-align:center; border:2px solid #e74c3c;">
                    <p style="font-weight:bold; font-size:16px; margin-bottom:8px;">After ({sim_days} 天後)</p>
                    <img src="{simulated_avatar_url}" width="200" style="object-fit:contain; height:220px; margin-bottom:8px;">
                    <p style="margin:0; font-size:14px; font-weight:bold;">{simulated_body_state}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # 2. 顯示漸進式 GIF 動畫 (與模擬結果連動)
        st.write("")
        progression_gif = get_body_progression_gif(gender)
        if progression_gif and os.path.exists(progression_gif):
            try:
                with open(progression_gif, "rb") as gif_file:
                    gif_bytes = gif_file.read()
                gif_base64 = base64.b64encode(gif_bytes).decode("utf-8")
                st.markdown(
                    f"""
                    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; width:100%; margin-top:20px; background:var(--secondary-background-color); padding:20px; border-radius:16px; border:1px solid rgba(255,75,75,0.3);">
                        <h4 style="margin-bottom:12px; color:#ff4b4b;">🎬 體態漸進變化過程動畫</h4>
                        <img src="data:image/gif;base64,{gif_base64}" style="width:340px; max-width:100%; height:auto; object-fit:contain; border-radius:12px;">
                        <p style="text-align:center; margin-top:12px; font-size:14px; opacity:0.8;">
                            經由每天 {total_day_cal:.0f} kcal 的累積，見證身材的動態轉變！
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            except Exception:
                pass
