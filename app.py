import base64
import datetime
import io
import os
import math
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
    .sim-card {
        background: var(--secondary-background-color);
        border-radius: 16px;
        padding: 16px;
        border: 1px solid rgba(52,152,219,0.35);
        margin-bottom: 12px;
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


# ==================== 固定體態 PNG + 漸進式 GIF ====================
# 固定 PNG 負責 BMI 對應人物；GIF 只負責播放體態漸進動畫。
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


@st.cache_data
def get_character_avatar_base64(gender, tier_idx):
    """依 BMI 體態等級直接讀取固定 PNG，不再從 GIF 猜 frame。"""
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


# ==================== 原本食物資料庫：完整保留，不刪除 ====================
TAIWAN_FOOD_DB = [
    # 早餐類
    {"name": "三明治 (Sandwich, 1份)", "cal": 320.0, "pro": 12.0, "carb": 35.0, "fat": 14.0},
    {"name": "蛋餅 (Dan Bing, 1份)", "cal": 300.0, "pro": 10.0, "carb": 35.0, "fat": 12.0},
    {"name": "飯糰 (Taiwanese Rice Ball, 1顆)", "cal": 420.0, "pro": 12.0, "carb": 58.0, "fat": 15.0},
    {"name": "燒餅油條 (Shaobing & Youtiao, 1份)", "cal": 550.0, "pro": 12.0, "carb": 60.0, "fat": 28.0},
    {"name": "蔥抓餅 (Scallion Pancake, 1份)", "cal": 380.0, "pro": 8.0, "carb": 48.0, "fat": 17.0},
    {"name": "蘿蔔糕 (Radish Cake, 2片)", "cal": 210.0, "pro": 4.0, "carb": 32.0, "fat": 7.0},
    {"name": "荷包蛋 (Fried Egg, 1顆)", "cal": 90.0, "pro": 6.5, "carb": 0.5, "fat": 7.0},
    {"name": "水煮蛋 (Boiled Egg, 1顆)", "cal": 72.0, "pro": 6.3, "carb": 0.4, "fat": 4.8},

    # 正餐與小吃類
    {"name": "三杯雞 (Three-Cup Chicken, 1份)", "cal": 480.0, "pro": 32.0, "carb": 8.0, "fat": 35.0},
    {"name": "滷肉飯 (Braised Pork Rice, 1碗)", "cal": 500.0, "pro": 15.0, "carb": 65.0, "fat": 20.0},
    {"name": "雞排 (Fried Chicken Cutlet, 1份)", "cal": 650.0, "pro": 35.0, "carb": 40.0, "fat": 42.0},
    {"name": "牛肉麵 (Beef Noodle Soup, 1碗)", "cal": 600.0, "pro": 28.0, "carb": 70.0, "fat": 22.0},
    {"name": "小籠包 (Xiao Long Bao, 8顆)", "cal": 520.0, "pro": 24.0, "carb": 48.0, "fat": 26.0},
    {"name": "陽春麵 (Plain Noodle Soup, 1碗)", "cal": 350.0, "pro": 10.0, "carb": 60.0, "fat": 7.0},
    {"name": "水餃 (Dumplings, 10顆)", "cal": 550.0, "pro": 22.0, "carb": 65.0, "fat": 22.0},
    {"name": "排骨飯 (Pork Chop Rice, 1份)", "cal": 750.0, "pro": 30.0, "carb": 85.0, "fat": 32.0},
    {"name": "雞腿飯 (Chicken Leg Rice, 1份)", "cal": 720.0, "pro": 35.0, "carb": 80.0, "fat": 28.0},
    {"name": "鍋貼 (Pan-fried Dumplings, 8顆)", "cal": 600.0, "pro": 18.0, "carb": 65.0, "fat": 30.0},
    {"name": "鹹酥雞 (Salt Crispy Chicken, 1份)", "cal": 550.0, "pro": 25.0, "carb": 30.0, "fat": 35.0},
    {"name": "蚵仔煎 (Oyster Omelet, 1份)", "cal": 450.0, "pro": 15.0, "carb": 50.0, "fat": 22.0},
    {"name": "肉圓 (Bawwan, 1顆)", "cal": 400.0, "pro": 12.0, "carb": 55.0, "fat": 15.0},
    {"name": "臭豆腐 (Stinky Tofu, 1份)", "cal": 420.0, "pro": 16.0, "carb": 30.0, "fat": 26.0},

    # 基礎食材與健康飲食
    {"name": "白米飯 (White Rice, 1碗)", "cal": 280.0, "pro": 5.4, "carb": 61.0, "fat": 0.6},
    {"name": "糙米飯 (Brown Rice, 1碗)", "cal": 250.0, "pro": 5.5, "carb": 52.0, "fat": 1.8},
    {"name": "水煮雞胸肉 (Chicken Breast, 100g)", "cal": 165.0, "pro": 31.0, "carb": 0.0, "fat": 3.6},
    {"name": "地瓜 (Sweet Potato, 1條)", "cal": 130.0, "pro": 2.2, "carb": 30.0, "fat": 0.3},
    {"name": "水煮青菜 (Boiled Veggies, 1盤)", "cal": 60.0, "pro": 2.5, "carb": 10.0, "fat": 1.5},
    {"name": "沙拉 (Vegetable Salad, 1份)", "cal": 120.0, "pro": 3.0, "carb": 15.0, "fat": 5.0},
    {"name": "鮭魚排 (Salmon, 120g)", "cal": 250.0, "pro": 24.0, "carb": 0.0, "fat": 16.0},

    # 飲料與甜點
    {"name": "珍珠奶茶 (Bubble Tea, 700ml/微糖)", "cal": 450.0, "pro": 4.0, "carb": 75.0, "fat": 15.0},
    {"name": "無糖豆漿 (Soy Milk, 500ml)", "cal": 175.0, "pro": 16.0, "carb": 10.0, "fat": 7.0},
    {"name": "鮮奶茶 (Milk Tea, 500ml)", "cal": 280.0, "pro": 8.0, "carb": 35.0, "fat": 11.0},
    {"name": "美式咖啡 (Black Coffee, 360ml)", "cal": 15.0, "pro": 1.0, "carb": 2.0, "fat": 0.0},
    {"name": "拿鐵 (Latte, 360ml)", "cal": 180.0, "pro": 9.0, "carb": 15.0, "fat": 9.0},
    {"name": "豆花 (Douhua, 1碗)", "cal": 250.0, "pro": 8.0, "carb": 40.0, "fat": 6.0},

    # 水果類
    {"name": "蘋果 (Apple, 1顆)", "cal": 78.0, "pro": 0.4, "carb": 21.0, "fat": 0.3},
    {"name": "香蕉 (Banana, 1根)", "cal": 105.0, "pro": 1.3, "carb": 27.0, "fat": 0.3},
    {"name": "芭樂 (Guava, 1顆)", "cal": 120.0, "pro": 2.5, "carb": 26.0, "fat": 1.0},
    {"name": "奇異果 (Kiwi, 2顆)", "cal": 90.0, "pro": 1.6, "carb": 22.0, "fat": 0.8},
    {"name": "木瓜 (Papaya, 1片)", "cal": 60.0, "pro": 0.8, "carb": 15.0, "fat": 0.3},

    # 速食與西式
    {"name": "大麥克漢堡 (Big Mac, 1個)", "cal": 590.0, "pro": 26.0, "carb": 46.0, "fat": 34.0},
    {"name": "薯條 (French Fries, 中份)", "cal": 380.0, "pro": 4.0, "carb": 48.0, "fat": 19.0},
    {"name": "披薩 (Pizza, 1片)", "cal": 280.0, "pro": 12.0, "carb": 30.0, "fat": 12.0},
    {"name": "義大利麵 (Pasta, 1份)", "cal": 520.0, "pro": 18.0, "carb": 70.0, "fat": 18.0},
]


# ==================== 食物資料庫擴充 ====================
# 完整資料放在 food_database.csv：共 10,000 筆。
# CSV 保留原本 44 筆資料，再加入常見早餐、便當、台灣小吃、日式、韓式、
# 西式、飲品、甜點、蔬菜、水果、肉類、海鮮、豆製品、零食等，以及常見份量變體。
# 其中擴充項目屬於飲食紀錄用估算值，實際熱量會依品牌、烹調方式與份量而不同。

ORIGINAL_FOOD_DB = [
    {"name": "三明治 (Sandwich, 1份)", "cal": 320.0, "pro": 12.0, "carb": 35.0, "fat": 14.0},
    {"name": "蛋餅 (Dan Bing, 1份)", "cal": 300.0, "pro": 10.0, "carb": 35.0, "fat": 12.0},
    {"name": "飯糰 (Taiwanese Rice Ball, 1顆)", "cal": 420.0, "pro": 12.0, "carb": 58.0, "fat": 15.0},
    {"name": "燒餅油條 (Shaobing & Youtiao, 1份)", "cal": 550.0, "pro": 12.0, "carb": 60.0, "fat": 28.0},
    {"name": "蔥抓餅 (Scallion Pancake, 1份)", "cal": 380.0, "pro": 8.0, "carb": 48.0, "fat": 17.0},
    {"name": "蘿蔔糕 (Radish Cake, 2片)", "cal": 210.0, "pro": 4.0, "carb": 32.0, "fat": 7.0},
    {"name": "荷包蛋 (Fried Egg, 1顆)", "cal": 90.0, "pro": 6.5, "carb": 0.5, "fat": 7.0},
    {"name": "水煮蛋 (Boiled Egg, 1顆)", "cal": 72.0, "pro": 6.3, "carb": 0.4, "fat": 4.8},
    {"name": "三杯雞 (Three-Cup Chicken, 1份)", "cal": 480.0, "pro": 32.0, "carb": 8.0, "fat": 35.0},
    {"name": "滷肉飯 (Braised Pork Rice, 1碗)", "cal": 500.0, "pro": 15.0, "carb": 65.0, "fat": 20.0},
    {"name": "雞排 (Fried Chicken Cutlet, 1份)", "cal": 650.0, "pro": 35.0, "carb": 40.0, "fat": 42.0},
    {"name": "牛肉麵 (Beef Noodle Soup, 1碗)", "cal": 600.0, "pro": 28.0, "carb": 70.0, "fat": 22.0},
    {"name": "小籠包 (Xiao Long Bao, 8顆)", "cal": 520.0, "pro": 24.0, "carb": 48.0, "fat": 26.0},
    {"name": "陽春麵 (Plain Noodle Soup, 1碗)", "cal": 350.0, "pro": 10.0, "carb": 60.0, "fat": 7.0},
    {"name": "水餃 (Dumplings, 10顆)", "cal": 550.0, "pro": 22.0, "carb": 65.0, "fat": 22.0},
    {"name": "排骨飯 (Pork Chop Rice, 1份)", "cal": 750.0, "pro": 30.0, "carb": 85.0, "fat": 32.0},
    {"name": "雞腿飯 (Chicken Leg Rice, 1份)", "cal": 720.0, "pro": 35.0, "carb": 80.0, "fat": 28.0},
    {"name": "鍋貼 (Pan-fried Dumplings, 8顆)", "cal": 600.0, "pro": 18.0, "carb": 65.0, "fat": 30.0},
    {"name": "鹹酥雞 (Salt Crispy Chicken, 1份)", "cal": 550.0, "pro": 25.0, "carb": 30.0, "fat": 35.0},
    {"name": "蚵仔煎 (Oyster Omelet, 1份)", "cal": 450.0, "pro": 15.0, "carb": 50.0, "fat": 22.0},
    {"name": "肉圓 (Bawwan, 1顆)", "cal": 400.0, "pro": 12.0, "carb": 55.0, "fat": 15.0},
    {"name": "臭豆腐 (Stinky Tofu, 1份)", "cal": 420.0, "pro": 16.0, "carb": 30.0, "fat": 26.0},
    {"name": "白米飯 (White Rice, 1碗)", "cal": 280.0, "pro": 5.4, "carb": 61.0, "fat": 0.6},
    {"name": "糙米飯 (Brown Rice, 1碗)", "cal": 250.0, "pro": 5.5, "carb": 52.0, "fat": 1.8},
    {"name": "水煮雞胸肉 (Chicken Breast, 100g)", "cal": 165.0, "pro": 31.0, "carb": 0.0, "fat": 3.6},
    {"name": "地瓜 (Sweet Potato, 1條)", "cal": 130.0, "pro": 2.2, "carb": 30.0, "fat": 0.3},
    {"name": "水煮青菜 (Boiled Veggies, 1盤)", "cal": 60.0, "pro": 2.5, "carb": 10.0, "fat": 1.5},
    {"name": "沙拉 (Vegetable Salad, 1份)", "cal": 120.0, "pro": 3.0, "carb": 15.0, "fat": 5.0},
    {"name": "鮭魚排 (Salmon, 120g)", "cal": 250.0, "pro": 24.0, "carb": 0.0, "fat": 16.0},
    {"name": "珍珠奶茶 (Bubble Tea, 700ml/微糖)", "cal": 450.0, "pro": 4.0, "carb": 75.0, "fat": 15.0},
    {"name": "無糖豆漿 (Soy Milk, 500ml)", "cal": 175.0, "pro": 16.0, "carb": 10.0, "fat": 7.0},
    {"name": "鮮奶茶 (Milk Tea, 500ml)", "cal": 280.0, "pro": 8.0, "carb": 35.0, "fat": 11.0},
    {"name": "美式咖啡 (Black Coffee, 360ml)", "cal": 15.0, "pro": 1.0, "carb": 2.0, "fat": 0.0},
    {"name": "拿鐵 (Latte, 360ml)", "cal": 180.0, "pro": 9.0, "carb": 15.0, "fat": 9.0},
    {"name": "豆花 (Douhua, 1碗)", "cal": 250.0, "pro": 8.0, "carb": 40.0, "fat": 6.0},
    {"name": "蘋果 (Apple, 1顆)", "cal": 78.0, "pro": 0.4, "carb": 21.0, "fat": 0.3},
    {"name": "香蕉 (Banana, 1根)", "cal": 105.0, "pro": 1.3, "carb": 27.0, "fat": 0.3},
    {"name": "芭樂 (Guava, 1顆)", "cal": 120.0, "pro": 2.5, "carb": 26.0, "fat": 1.0},
    {"name": "奇異果 (Kiwi, 2顆)", "cal": 90.0, "pro": 1.6, "carb": 22.0, "fat": 0.8},
    {"name": "木瓜 (Papaya, 1片)", "cal": 60.0, "pro": 0.8, "carb": 15.0, "fat": 0.3},
    {"name": "大麥克漢堡 (Big Mac, 1個)", "cal": 590.0, "pro": 26.0, "carb": 46.0, "fat": 34.0},
    {"name": "薯條 (French Fries, 中份)", "cal": 380.0, "pro": 4.0, "carb": 48.0, "fat": 19.0},
    {"name": "披薩 (Pizza, 1片)", "cal": 280.0, "pro": 12.0, "carb": 30.0, "fat": 12.0},
    {"name": "義大利麵 (Pasta, 1份)", "cal": 520.0, "pro": 18.0, "carb": 70.0, "fat": 18.0},
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


@st.cache_data

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
            "category": "智慧推估",
        }]
    return results[:80]


def search_taiwan_food(keyword):
    return search_foods(keyword)


# ==================== 版面配置：左側基本資料與數值，右側角色卡片 ====================
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.markdown("### 📋 基本資料")
    char_name = st.text_input("角色名稱", value="小勇士")
    col_s1, col_s2 = st.columns(2)

    with col_s1:
        age = st.number_input("年齡 (歲)", min_value=1, max_value=120, value=25)
        height = st.number_input("身高 (cm)", min_value=50.0, max_value=230.0, value=150.0)
        target_weight = st.number_input("目標體重 (kg)", min_value=20.0, max_value=250.0, value=45.0)

        # 新增：目標期限，位置緊接在目標體重下一欄
        target_weeks = st.number_input(
            "目標期限 (週)",
            min_value=1,
            max_value=520,
            value=12,
            step=1,
            help="設定預計多久達到目標體重。系統會依目前體重、目標體重與期限估算每日熱量差。",
        )

    with col_s2:
        gender = st.selectbox("性別", ["女", "男"])
        weight = st.number_input(
            "目前體重 (kg)",
            min_value=20.0,
            max_value=250.0,
            value=50.0,
        )

# 計算 BMR, TDEE, BMI
if gender == "女":
    bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
else:
    bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5

tdee = bmr * 1.2
bmi = weight / ((height / 100) ** 2)
recommended_water = max(1500, weight * 35 + (height - 150) * 3)

today_cal_sum = sum(item["cal"] for item in st.session_state.history)
calorie_remaining = tdee - today_cal_sum


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


def estimate_goal_plan(current_weight, goal_weight, weeks, daily_tdee, current_bmi):
    days = max(1, weeks * 7)
    weight_delta = current_weight - goal_weight
    required_daily_deficit = (weight_delta * 7700) / days

    # 以 500 kcal/day 作為較保守的展示上限；若目標要求更快，提醒延長期限。
    safe_demo_deficit = min(max(required_daily_deficit, 0), 500)
    suggested_daily_intake = max(1200, daily_tdee - safe_demo_deficit)

    if abs(weight_delta) < 0.1:
        return {
            "direction": "維持",
            "required": 0,
            "suggested": daily_tdee,
            "rate": 0,
            "message": "目前體重已接近目標體重，可以把重點放在維持規律飲食、活動量與水分。",
            "warning": None,
        }

    if weight_delta > 0:
        weekly_rate = weight_delta / weeks
        warning = None
        if weekly_rate > 1.0:
            warning = "目前期限需要的減重速度偏快，建議把期限拉長，不要用極端節食方式追趕目標。"
        return {
            "direction": "減重",
            "required": required_daily_deficit,
            "suggested": suggested_daily_intake,
            "rate": weekly_rate,
            "message": (
                f"預計每週約下降 {weekly_rate:.2f} kg。"
                f"以目前估算 TDEE 計算，平均每日攝取約 {suggested_daily_intake:.0f} kcal 可作為展示上的規劃起點，"
                "並搭配規律活動與均衡飲食。"
            ),
            "warning": warning,
        }

    weekly_rate = abs(weight_delta) / weeks
    return {
        "direction": "增重",
        "required": abs(required_daily_deficit),
        "suggested": daily_tdee + min(abs(required_daily_deficit), 300),
        "rate": weekly_rate,
        "message": (
            f"預計每週約增加 {weekly_rate:.2f} kg。"
            "建議以均衡飲食、足量蛋白質與規律阻力訓練為主，不以高糖高油食物硬湊熱量。"
        ),
        "warning": None,
    }


goal_plan = estimate_goal_plan(
    weight, target_weight, int(target_weeks), tdee, bmi
)

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

# 新增：目標體重規劃
st.write("")
st.markdown("### 🎯 目標體重規劃")
goal_col1, goal_col2, goal_col3 = st.columns(3)
goal_col1.metric("目標體重", f"{target_weight:.1f} kg")
goal_col2.metric("預計期限", f"{int(target_weeks)} 週")
goal_col3.metric("每週變化", f"{goal_plan['rate']:.2f} kg")

if goal_plan["direction"] == "減重":
    st.info(
        f"💡 目標差距：{weight - target_weight:.1f} kg｜"
        f"展示用每日熱量規劃：約 {goal_plan['suggested']:.0f} kcal"
    )
elif goal_plan["direction"] == "增重":
    st.info(
        f"💡 目標差距：{target_weight - weight:.1f} kg｜"
        f"展示用每日熱量規劃：約 {goal_plan['suggested']:.0f} kcal"
    )
else:
    st.success("✨ 目前體重已接近目標，可以把重點放在維持。")

st.markdown(
    f"""
    <div class="goal-card">
        <strong>💬 減肥建議</strong><br>
        {goal_plan["message"]}
    </div>
    """,
    unsafe_allow_html=True,
)

if goal_plan["warning"]:
    st.warning(f"⚠️ {goal_plan['warning']}")

# 數據小卡列
st.write("")
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("基礎代謝 (BMR)", f"{bmr:.0f} kcal")
col_m2.metric("每日消耗 (TDEE)", f"{tdee:.0f} kcal")
col_m3.metric("目前 BMI", f"{bmi:.1f}")
col_m4.metric("今日剩餘熱量", f"{calorie_remaining:.0f} kcal")

st.info(f"💬 {st.session_state.last_feedback}")
st.divider()

# 分頁架構：刪除原本的「歷史熱量圖表」，其他標題名稱不變
tab1, tab2, tab3 = st.tabs(
    ["🍱 三餐紀錄", "💧 水分與日常追蹤", "🤖 今天這樣吃好嗎"]
)


# 關鍵字搜尋與自動帶入模組
def render_food_selector_section(unique_key_prefix):
    st.markdown("#### 關鍵字搜尋")
    st.caption(f"🍱 食物資料庫：{len(TAIWAN_FOOD_DB):,} 筆（原有資料完整保留）")
    search_keyword = st.text_input(
        "輸入關鍵字", "", key=f"{unique_key_prefix}_kw"
    )

    matched_foods = search_taiwan_food(search_keyword)
    options = [f["name"] for f in matched_foods]
    options.append("✏️ 自訂食物與營養素 (手動輸入)")

    sel_key = f"{unique_key_prefix}_sel"
    prev_sel_key = f"{unique_key_prefix}_prev_sel"

    selected_option = st.selectbox(
        "選擇搜尋結果", options, key=sel_key
    )

    if selected_option == "✏️ 自訂食物與營養素 (手動輸入)":
        f_name = "自訂健康餐點"
        default_cal, default_pro, default_carb, default_fat = (
            350.0, 15.0, 40.0, 12.0
        )
    else:
        matched_item = next(
            (f for f in matched_foods if f["name"] == selected_option),
            (
                matched_foods[0]
                if matched_foods
                else {
                    "name": "自訂",
                    "cal": 350.0,
                    "pro": 15.0,
                    "carb": 40.0,
                    "fat": 12.0,
                }
            ),
        )
        f_name = matched_item["name"]
        default_cal = matched_item["cal"]
        default_pro = matched_item["pro"]
        default_carb = matched_item["carb"]
        default_fat = matched_item["fat"]

    if (
        prev_sel_key not in st.session_state
        or st.session_state[prev_sel_key] != selected_option
    ):
        st.session_state[f"{unique_key_prefix}_fcal"] = float(default_cal)
        st.session_state[f"{unique_key_prefix}_fpro"] = float(default_pro)
        st.session_state[f"{unique_key_prefix}_fcarb"] = float(default_carb)
        st.session_state[f"{unique_key_prefix}_ffat"] = float(default_fat)
        st.session_state[prev_sel_key] = selected_option
        st.rerun()

    c1, c2, c3, c4 = st.columns(4)
    f_cal = c1.number_input(
        "熱量 (kcal)", key=f"{unique_key_prefix}_fcal", min_value=0.0
    )
    f_pro = c2.number_input(
        "蛋白質 (g)", key=f"{unique_key_prefix}_fpro", min_value=0.0
    )
    f_carb = c3.number_input(
        "碳水 (g)", key=f"{unique_key_prefix}_fcarb", min_value=0.0
    )
    f_fat = c4.number_input(
        "脂肪 (g)", key=f"{unique_key_prefix}_ffat", min_value=0.0
    )

    return f_name, f_cal, f_pro, f_carb, f_fat


# 分頁一：三餐紀錄
with tab1:
    st.subheader("📝 三餐與營養素記錄")
    meal_category = st.selectbox(
        "選擇餐別", ["早餐", "午餐", "晚餐", "宵夜"]
    )

    food_name, food_cal, food_pro, food_carb, food_fat = (
        render_food_selector_section("tab1")
    )

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

        new_total = sum(item["cal"] for item in st.session_state.history)

        if new_total > tdee + 200:
            st.session_state.last_feedback = (
                f"⚠️ 警告！熱量超載！『{char_name}』的防禦力快被油膩吞沒了，要控制囉！"
            )
        elif new_total >= tdee - 100:
            st.session_state.last_feedback = (
                f"✨ 營養攝取非常均衡，『{char_name}』狀態極佳！"
            )
        else:
            st.session_state.last_feedback = (
                f"🌟 太神啦！目前維持完美的熱量赤字，『{char_name}』正在持續變強中！"
            )

        st.success(f"成功記錄！『{char_name}』的冒險日誌已更新。")
        st.rerun()

    if st.session_state.history:
        st.write("### 📋 今日飲食清單")
        st.dataframe(
            pd.DataFrame(st.session_state.history),
            use_container_width=True,
        )


# 分頁二：水分與日常追蹤
with tab2:
    st.subheader("💧 每日水分攝取量追蹤")
    st.info(
        f"💡 根據您的身高 (**{height} cm**) 與體重 (**{weight} kg**) 計算，"
        f"今日建議飲水量為：**{recommended_water:.0f} c.c.**"
    )

    st.write(
        f"目前已補充水分：**{st.session_state.water} c.c.** / 目標 "
        f"**{recommended_water:.0f} c.c.**"
    )

    col_w1, col_w2, col_w3 = st.columns(3)

    if col_w1.button("💧 喝一杯水 (+250 c.c.)"):
        st.session_state.water += 250
        st.session_state.water_history.append({
            "date": str(datetime.date.today()),
            "action": "喝一杯水",
            "amount": "250 c.c.",
            "total_water": f"{st.session_state.water} c.c.",
        })
        st.success("成功記錄 250 c.c. 水分！")
        st.rerun()

    if col_w2.button("🚰 大口灌水 (+500 c.c.)"):
        st.session_state.water += 500
        st.session_state.water_history.append({
            "date": str(datetime.date.today()),
            "action": "大口灌水",
            "amount": "500 c.c.",
            "total_water": f"{st.session_state.water} c.c.",
        })
        st.success("成功記錄 500 c.c. 水分！")
        st.rerun()

    if col_w3.button("🔄 重置水分歸零"):
        st.session_state.water = 0
        st.session_state.water_history = []
        st.success("水分紀錄已重置歸零！")
        st.rerun()

    if st.session_state.water < recommended_water:
        st.warning(
            "⚠️ 警告：角色出現『缺水 Debuff』，代謝速度下降中，請趕快多喝水！"
        )
    else:
        st.success(
            "🌟 狀態加成：水分充足，獲得『水潤新陳代謝 Buff』！"
        )

    st.write("### 📋 飲水紀錄")
    if st.session_state.water_history:
        st.dataframe(
            pd.DataFrame(st.session_state.water_history),
            use_container_width=True,
        )
    else:
        st.info("目前尚無飲水紀錄，點擊上方按鈕開始記錄水分吧！")


# 分頁三：今天這樣吃好嗎
with tab3:
    st.subheader("🤖 今天這樣吃好嗎")
    st.info(
        "💡 💡 選擇早餐、午餐、晚餐，系統會整理全天營養素，並模擬「如果長期維持今天的吃法」可能出現的體態變化。"
    )

    st.markdown("---")
    st.markdown("#### 🍳 早餐：吃了甚麼")
    bf_name, bf_cal, bf_pro, bf_carb, bf_fat = (
        render_food_selector_section("tab4_breakfast")
    )

    st.markdown("---")
    st.markdown("#### 🍱 午餐：吃了甚麼")
    lu_name, lu_cal, lu_pro, lu_carb, lu_fat = (
        render_food_selector_section("tab4_lunch")
    )

    st.markdown("---")
    st.markdown("#### 🍲 晚餐：吃了甚麼")
    di_name, di_cal, di_pro, di_carb, di_fat = (
        render_food_selector_section("tab4_dinner")
    )

    total_day_cal = bf_cal + lu_cal + di_cal
    total_day_pro = bf_pro + lu_pro + di_pro
    total_day_carb = bf_carb + lu_carb + di_carb
    total_day_fat = bf_fat + lu_fat + di_fat

    st.markdown("---")
    st.markdown("#### 📊 全天總計欄位")
    c_t1, c_t2, c_t3, c_t4 = st.columns(4)
    c_t1.metric("總熱量", f"{total_day_cal:.0f} kcal")
    c_t2.metric("總蛋白質", f"{total_day_pro:.1f} g")
    c_t3.metric("總碳水", f"{total_day_carb:.1f} g")
    c_t4.metric("總脂肪", f"{total_day_fat:.1f} g")

    # 新增：長期熱量累積模擬
    st.markdown("---")
    st.markdown("#### 🔮 熱量累積與體態變化模擬")

    sim_days = st.slider(
        "如果連續維持今天的飲食量，想看看未來多久的變化？",
        min_value=7,
        max_value=180,
        value=30,
        step=7,
    )

    simulated_daily_balance = total_day_cal - tdee
    simulated_weight_long = weight + (
        simulated_daily_balance * sim_days / 7700
    )
    simulated_weight_long = max(20.0, simulated_weight_long)
    simulated_bmi_long = simulated_weight_long / ((height / 100) ** 2)
    simulated_tier_long, simulated_state_long = get_body_tier(simulated_bmi_long)

    s1, s2, s3 = st.columns(3)
    s1.metric("每日熱量差", f"{simulated_daily_balance:+.0f} kcal")
    s2.metric(f"{sim_days} 天後估算體重", f"{simulated_weight_long:.1f} kg")
    s3.metric("估算 BMI", f"{simulated_bmi_long:.1f}")

    if simulated_daily_balance > 0:
        st.warning(
            f"⚠️ 如果長期每天維持約 {total_day_cal:.0f} kcal，"
            f"目前模型估算 {sim_days} 天後可能增加約 "
            f"{simulated_weight_long - weight:.1f} kg。"
            "這是簡化的能量平衡示意，不代表實際身體一定會如此變化。"
        )
    elif simulated_daily_balance < 0:
        st.success(
            f"🌱 如果長期維持今天的攝取量，模型估算 {sim_days} 天後約為 "
            f"{simulated_weight_long:.1f} kg。實際體重仍會受到活動量、睡眠、"
            "水分與個體差異影響。"
        )
    else:
        st.info("⚖️ 今天的攝取量約等於目前估算的 TDEE，模型中的體重維持不變。")

    # 漸進式 GIF：改用 Base64 HTML 顯示，避開 Streamlit / Pillow 對 GIF 的解析問題
    progression_gif = get_body_progression_gif(gender)
    if progression_gif and os.path.exists(progression_gif):
        try:
            with open(progression_gif, "rb") as gif_file:
                gif_bytes = gif_file.read()

            gif_base64 = base64.b64encode(gif_bytes).decode("utf-8")

            st.markdown(
                f"""
                <div style="
                    display:flex;
                    flex-direction:column;
                    align-items:center;
                    justify-content:center;
                    width:100%;
                ">
                    <img
                        src="data:image/gif;base64,{gif_base64}"
                        style="
                            width:360px;
                            max-width:100%;
                            height:auto;
                            object-fit:contain;
                            border-radius:16px;
                        "
                    >
                    <p style="
                        text-align:center;
                        margin-top:10px;
                        font-size:14px;
                        opacity:0.8;
                    ">
                        漸進式體態變化示意：很瘦 → 瘦 → 正常 → 微胖 → 很胖
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.caption(
                "GIF 只負責播放漸進動畫；主人物與 Before / After 皆由固定 PNG 依 BMI 等級顯示。"
            )
        except Exception as e:
            st.warning(
                "體態動畫目前無法載入，但不影響主人物與 Before / After 體態模擬。"
            )
    else:
        st.info(
            "尚未找到漸進式體態 GIF。請將 female_body_progression.gif / "
            "male_body_progression.gif 放入 images 資料夾。"
        )

    if st.button("🚀 啟動模擬分析與建議", type="primary"):
        st.write("---")
        st.markdown(f"### 🛡️ 【{char_name}】的 模擬分析")

        projected_remaining = tdee - total_day_cal

        # Before/After 保留，人物改用固定 PNG 依 BMI 等級直接對應
        simulated_weight = simulated_weight_long
        simulated_bmi = simulated_bmi_long
        simulated_tier, simulated_body_state = get_body_tier(simulated_bmi)

        if projected_remaining < 0:
            simulated_body_state += " (⚠️ 熱量超載警戒)"

        simulated_avatar_url = get_character_avatar_base64(
            gender, simulated_tier
        )

        st.markdown("#### Before vs After")
        col_img1, col_img2 = st.columns(2)

        with col_img1:
            st.markdown(
                f"""
                <div style="background:var(--secondary-background-color);
                            padding:15px; border-radius:12px; text-align:center;
                            border:2px solid #3498db;">
                    <p style="font-weight:bold; font-size:15px; margin-bottom:8px;">
                        Before
                    </p>
                    <img src="{current_avatar_url}" width="200"
                         style="object-fit:contain; height:220px; margin-bottom:8px;">
                    <p style="margin:0; font-size:14px; font-weight:bold;">
                        {body_state}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_img2:
            st.markdown(
                f"""
                <div style="background:var(--secondary-background-color);
                            padding:15px; border-radius:12px; text-align:center;
                            border:2px solid #e74c3c;">
                    <p style="font-weight:bold; font-size:15px; margin-bottom:8px;">
                        After
                    </p>
                    <img src="{simulated_avatar_url}" width="200"
                         style="object-fit:contain; height:220px; margin-bottom:8px;">
                    <p style="margin:0; font-size:14px; font-weight:bold;">
                        {simulated_body_state}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.info(
            f"🔎 模擬期間：{sim_days} 天｜"
            f"模型估算體重：{weight:.1f} → {simulated_weight:.1f} kg｜"
            f"BMI：{bmi:.1f} → {simulated_bmi:.1f}"
        )

        st.markdown("#### 小建議")
        if projected_remaining >= 150:
            st.success(
                "🌟 今天的熱量仍有空間。建議優先補足蛋白質、蔬菜與高纖主食，"
                "不用刻意用零食把熱量補滿。"
            )
        elif projected_remaining >= 0:
            st.warning(
                "⚠️ 今天的熱量接近 TDEE 邊界。建議控制高油、高糖飲品與宵夜，"
                "並維持日常活動量。"
            )
        else:
            st.error(
                "🚨 今天估算攝取量高於 TDEE 約 "
                f"**{abs(projected_remaining):.0f} kcal**。"
                "偶爾超過一天不代表立刻變胖，真正需要注意的是長期累積。"
                "可以從減少高熱量飲品、調整份量與增加日常活動開始。"
            )

        # 目標期限建議
        if goal_plan["direction"] == "減重":
            st.markdown("#### 🎯 目標期限建議")
            if goal_plan["warning"]:
                st.warning(
                    f"{goal_plan['warning']} "
                    f"目前設定為 {int(target_weeks)} 週，"
                    f"若拉長期限，通常會更容易把飲食與活動安排得穩定。"
                )
            else:
                st.success(
                    f"依目前設定，目標是 {int(target_weeks)} 週減少 "
                    f"{weight - target_weight:.1f} kg，"
                    f"平均每週約 {goal_plan['rate']:.2f} kg。"
                )
        elif goal_plan["direction"] == "增重":
            st.markdown("#### 🎯 目標期限建議")
            st.info(
                f"目標期限為 {int(target_weeks)} 週，"
                f"平均每週約增加 {goal_plan['rate']:.2f} kg。"
            )
