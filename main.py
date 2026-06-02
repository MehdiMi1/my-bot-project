import os
import json
import uuid
import logging
import urllib.request
import re
import random
import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters,
)
from PIL import Image

from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

# --- سرور فیک برای بیدار نگه داشتن ربات در رندر ---
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), KeepAliveHandler)
    server.serve_forever()

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()
# ---------------------------------------------------

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- تمام وضعیت‌های سیستم ---
(CHOOSING, COLLECTING_PHOTOS, SELECTING_MAJOR, SELECTING_SUB_MAJOR, GETTING_NAME, GETTING_USER_MAJOR, 
 SEARCHING, ACTION_MENU, EDU_SERVICES_MENU, WAITING_FOR_SUBMISSION, 
 SURVEY_TEACHER, SURVEY_COURSE, SURVEY_BEHAVIOR, SURVEY_ATTENDANCE, SURVEY_GRADING, SURVEY_MATERIAL, SURVEY_RATING,
 EMP_TITLE, EMP_SKILLS, EMP_LEVEL, EMP_CONTACT, GPA_INPUT, 
 HEALTH_MOOD, HEALTH_HEIGHT, HEALTH_WEIGHT, CONTACT_ADMIN_MSG, WAITING_FOR_MAP_PHOTO,
 MUSIC_CATEGORY, MUSIC_TITLE, MUSIC_REVIEW, MUSIC_RATING) = range(31)

# 🔴 تنظیمات لیارا (تغییر مسیر فایل‌ها به پوشه data)
DATA_DIR = "data"
if not os.path.exists(DATA_DIR): 
    os.makedirs(DATA_DIR)

DB_FILE = os.path.join(DATA_DIR, "users_db.json")
CONTENT_DB_FILE = os.path.join(DATA_DIR, "content_db.json") 
TEACHERS_DB_FILE = os.path.join(DATA_DIR, "teachers_db.json")
SETTINGS_DB_FILE = os.path.join(DATA_DIR, "settings_db.json")

TEMP_DIR = os.path.join(DATA_DIR, "temp_photos")
if not os.path.exists(TEMP_DIR): 
    os.makedirs(TEMP_DIR)

# 🔴 تنظیمات ادمین و کانال اصلی
ADMIN_ID = 427506502  
CHANNEL_ID = "@Uniazadkaraj_Asatid"

pending_submissions = {}

def load_db(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def save_db(data, file_name):
    with open(file_name, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

content_db = load_db(CONTENT_DB_FILE)
if not content_db:
    content_db = {
        "رادار زنده کلاس‌ها 📡": {}, "گروه‌های درسی 🔗": {}, "بازارچه دانشجویی 🛒": {}, 
        "مطالب و جزوات 📚": {}, "شماره‌های آموزش 📞": {}, "موسیقی و سینما 🎬🎵": {}
    }
    save_db(content_db, CONTENT_DB_FILE)

def update_user_activity(user_id, username, name, major):
    db = load_db(DB_FILE)
    uid = str(user_id)
    if uid not in db: db[uid] = {}
    db[uid]['name'] = name
    db[uid]['major'] = major
    db[uid]['username'] = username if username else "ندارد"
    db[uid]['last_active'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_db(db, DB_FILE)

def get_shamsi_date():
    now = datetime.datetime.now()
    g_y, g_m, g_d = now.year, now.month, now.day
    d_4 = g_y % 4
    g_a = [0, 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    doy_g = g_a[g_m] + g_d
    if d_4 == 0 and g_m > 2: doy_g += 1
    d_33 = int(((g_y - 16) % 132) * 0.0305)
    a = 286 if (d_33 == 3 or d_33 < (d_4 - 1) or d_4 == 0) else 287
    if (d_33 == 1 or d_33 == 2) and (d_33 == d_4 or d_4 == 1): b = 78
    else: b = 80 if (d_33 == 3 and d_4 == 0) else 79
    if int((g_y - 10) / 63) == 30: a -= 1; b += 1
    if doy_g > b:
        jy = g_y - 621
        doy_j = doy_g - b
    else:
        jy = g_y - 622
        doy_j = doy_g + a
    if doy_j < 187:
        jm = int((doy_j - 1) / 31) + 1
        jd = (doy_j - 1) % 31 + 1
    else:
        jm = int((doy_j - 187) / 30) + 7
        jd = (doy_j - 187) % 30 + 1
    
    weekdays = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یک‌شنبه"]
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    weekday_name = weekdays[now.weekday()]
    return f"{weekday_name} {jd} {months[jm-1]} {jy}"

def fetch_latest_configs():
    try:
        req = urllib.request.Request("https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            html = response.read().decode('utf-8')
            links = re.findall(r'(vless://[^\s]+|vmess://[^\s]+)', html)
            if links: return links[:3]
    except: pass
    uid = str(uuid.uuid4())[:8]
    return [
        f"vless://{uid}@1.1.1.1:443?encryption=none&security=tls&sni=cloudflare.com&fp=chrome&type=ws&host=cloudflare.com&path=%2F#Azad_Karaj_Public_VIP_1",
        f"vless://{uid}a@8.8.8.8:443?encryption=none&security=tls&sni=google.com&fp=chrome&type=ws&host=google.com&path=%2F#Azad_Karaj_Public_VIP_2"
    ]

def fetch_news():
    try:
        req = urllib.request.Request("https://www.isna.ir/rss/tp/34", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            xml = response.read().decode('utf-8')
        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', xml)
        if len(titles) > 1: return titles[1:6]
        return ["در حال حاضر خبر جدیدی در دسترس نیست."]
    except: return ["ارتباط با سرور اخبار برقرار نشد."]

MAIN_KEYBOARD = [
    ["کانفیگ‌های پرسرعت 🌐", "اخبار 🗞️"],
    ["رادار زنده کلاس‌ها 📡", "گروه‌های درسی 🔗"],
    ["خدمات آموزشی 🎓", "بانک نظرات 🔍"],
    ["استخدام 💼", "بازارچه دانشجویی 🛒"],
    ["نظرسنجی اساتید ✍️", "معدل‌گیر پیشرفته 🧮"],
    ["موسیقی و سینما 🎬🎵", "سلامت من (AI) ⏱️"],
    ["نقشه دانشگاه 🗺️", "ارتباط با ادمین 📞"],
    ["برترین‌ها 🏆", "پروفایل 👤", "📸 عکس به PDF"],
    ["تنظیمات من ⚙️", "پنل ادمین 👑", "معرفی به دوستان 🚀"]
]

MAJORS_KEYBOARD = [
    ["روانشناسی 🧠", "مهندسی کامپیوتر 💻", "حقوق ⚖️"],
    ["مدیریت 📈", "حسابداری 📊", "معماری 🏛️"],
    ["مهندسی عمران 🏗️", "آموزش زبان 🇬🇧", "علوم پزشکی 🩺"],
    ["مهندسی برق ⚡", "مهندسی مکانیک ⚙️", "تربیت بدنی ⚽"],
    ["علوم پایه 🔬", "دامپزشکی 🐕", "هنر و رسانه 🎨"],
    ["مهندسی صنایع 🏭", "کشاورزی 🌾"],
    ["🔙 بازگشت به منوی اصلی"]
]

SUB_MAJORS = {
    "روانشناسی 🧠": [["روانشناسی (گرایش اصلی)"], ["بالینی", "عمومی"], ["تربیتی", "صنعتی و سازمانی"], ["کودکان استثنایی"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "مهندسی کامپیوتر 💻": [["مهندسی کامپیوتر (گرایش اصلی)"], ["نرم‌افزار", "فناوری اطلاعات (IT)"], ["هوش مصنوعی", "سخت‌افزار", "شبکه"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "حقوق ⚖️": [["حقوق (گرایش اصلی)"], ["حقوق خصوصی", "حقوق جزا"], ["حقوق عمومی", "حقوق بین‌الملل"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "مدیریت 📈": [["مدیریت (گرایش اصلی)"], ["بازرگانی", "صنعتی"], ["مالی", "دولتی"], ["اجرایی (EMBA)"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "حسابداری 📊": [["حسابداری (گرایش اصلی)"], ["حسابداری مالی", "حسابرسی"], ["حسابداری مدیریت", "حسابداری مالیاتی"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "معماری 🏛️": [["معماری (گرایش اصلی)"], ["مهندسی معماری", "معماری داخلی"], ["مرمت بناها", "شهرسازی"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "مهندسی عمران 🏗️": [["عمران (گرایش اصلی)"], ["عمران-عمران", "نقشه‌برداری"], ["سازه", "زلزله"], ["ژئوتکنیک", "مدیریت ساخت"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "آموزش زبان 🇬🇧": [["زبان انگلیسی (گرایش اصلی)"], ["مترجمی زبان", "آموزش زبان"], ["ادبیات انگلیسی", "زبان آلمانی"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "علوم پزشکی 🩺": [["پزشکی (گرایش اصلی)"], ["پرستاری", "مامایی"], ["علوم آزمایشگاهی", "اتاق عمل", "هوشبری"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "دامپزشکی 🐕": [["دامپزشکی (گرایش اصلی)"], ["علوم درمانگاهی", "پاتوبیولوژی"], ["بهداشت مواد غذایی"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "علوم پایه 🔬": [["علوم پایه (گرایش اصلی)"], ["شیمی", "فیزیک"], ["ریاضی", "زیست‌شناسی"], ["ژنتیک", "میکروبیولوژی"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "کشاورزی 🌾": [["کشاورزی (گرایش اصلی)"], ["زراعت", "گیاه‌پزشکی"], ["علوم دامی", "صنایع غذایی"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "هنر و رسانه 🎨": [["هنر (گرایش اصلی)"], ["گرافیک", "نقاشی"], ["سینما", "عکاسی"], ["طراحی لباس", "انیمیشن"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "مهندسی برق ⚡": [["مهندسی برق (گرایش اصلی)"], ["الکترونیک", "قدرت"], ["کنترل", "مخابرات"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "مهندسی مکانیک ⚙️": [["مهندسی مکانیک (گرایش اصلی)"], ["سیالات", "جامدات"], ["ساخت و تولید", "خودرو"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "مهندسی صنایع 🏭": [["مهندسی صنایع (گرایش اصلی)"], ["بهینه‌سازی سیستم‌ها", "مدیریت مهندسی"], ["🔙 بازگشت به لیست رشته‌ها"]],
    "تربیت بدنی ⚽": [["تربیت بدنی (گرایش اصلی)"], ["فیزیولوژی ورزشی", "مدیریت ورزشی"], ["آسیب‌شناسی حرکتی"], ["🔙 بازگشت به لیست رشته‌ها"]]
}

def get_action_keyboard(user_id):
    keyboard = [["👀 مشاهده اطلاعات این بخش"], ["➕ ثبت اطلاعات جدید"]]
    if user_id == ADMIN_ID:
        keyboard.append(["⚡️ ثبت مستقیم و فوری (ویژه ادمین)"])
    keyboard.append(["🔙 بازگشت به منوی اصلی"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

EDU_SUB_KEYBOARD = [["📚 مطالب و جزوات", "📞 شماره‌های آموزش"], ["🌐 سایت‌های مهم دانشجویی"], ["🔙 بازگشت به منوی اصلی"]]
MUSIC_CAT_KEYBOARD = [["🎵 موسیقی و آهنگ", "🎬 فیلم و سریال"], ["🔙 بازگشت به منوی اصلی"]]

POEMS = [
    "بنی آدم اعضای یکدیگرند / که در آفرینش ز یک گوهرند 🌸",
    "روزگار است این که گه عزت دهد گه خوار دارد / چرخ بازیگر از این بازیچه‌ها بسیار دارد 🍃",
    "هر کسی کو دور ماند از اصل خویش / باز جوید روزگار وصل خویش ✨",
    "تو نیکی می‌کن و در دجله انداز / که ایزد در بیابانت دهد باز 🌊",
    "صبر و ظفر هر دو دوستان قدیمند / بر اثر صبر نوبت ظفر آید 🕊",
    "در ناامیدی بسی امید است / پایان شب سیه سپید است 🌙",
    "آسایش دو گیتی تفسیر این دو حرف است / با دوستان مروت با دشمنان مدارا 🤝",
    "از صدای سخن عشق ندیدم خوشتر / یادگاری که در این گنبد دوار بماند ❤️",
    "رسید مژده که ایام غم نخواهد ماند / چنان نماند چنین نیز هم نخواهد ماند 🌤"
]

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False) -> bool:
    user_id = update.callback_query.from_user.id if is_callback else update.message.from_user.id
    if user_id == ADMIN_ID: return True
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['left', 'kicked']:
            keyboard = [
                [InlineKeyboardButton("✅ عضویت اجباری در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")],
                [InlineKeyboardButton("🔄 عضو شدم", callback_data="verify_join")]
            ]
            text = "🛑 **دسترسی شما محدود شده است!**\n\nبرای استفاده از ربات، ابتدا در کانال رسمی ما عضو شوید، سپس روی دکمه «عضو شدم» کلیک کنید تا ربات به صورت خودکار برای شما فعال شود."
            if is_callback:
                await update.callback_query.answer("شما هنوز عضو کانال نشده‌اید!", show_alert=True)
            else:
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            return False
        return True
    except Exception as e:
        return True

async def send_welcome(message_obj, context, user):
    today_date = get_shamsi_date()
    poem = random.choice(POEMS)
    db = load_db(DB_FILE)
    uid = str(user.id)
    if uid in db: 
        update_user_activity(uid, user.username, db[uid].get('name',''), db[uid].get('major',''))
    welcome_msg = (
        f"📅 **تاریخ:** {today_date}\n"
        f"📜 **بیت روز:**\n_{poem}_\n\n"
        "🎓 به سوپراپلیکیشن پیشرفته دانشجویی دانشگاه آزاد کرج خوش آمدید!\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:"
    )
    await message_obj.reply_text(welcome_msg, reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True), parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_join(update, context): return CHOOSING
    await send_welcome(update.message, context, update.message.from_user)
    return CHOOSING

async def verify_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status not in ['left', 'kicked']:
            await query.message.delete()
            await send_welcome(query.message, context, query.from_user)
            return CHOOSING
        else:
            await query.answer("❌ هنوز عضو کانال نشده‌اید! لطفاً ابتدا عضو شوید.", show_alert=True)
    except Exception as e:
        await query.answer("خطایی رخ داد، لطفاً دوباره تلاش کنید.", show_alert=True)
    return CHOOSING

async def fetch_channel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("لطفاً آیدی کانال را وارد کنید.\nمثال: `/fetch_channel @username`", parse_mode='Markdown')
        return
    channel_username = context.args[0]
    await update.message.reply_text(f"⏳ در حال استخراج و تحلیل آخرین مطالب از {channel_username}...\n(این ویژگی فوق‌حرفه‌ای در فاز توسعه قرار دارد و به زودی دیتای استخراج شده را مستقیماً برای تایید به شما نمایش می‌دهد.)")

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_join(update, context): return CHOOSING
    user_text = update.message.text
    needs_major_selection = ["رادار زنده کلاس‌ها 📡", "گروه‌های درسی 🔗", "بازارچه دانشجویی 🛒", "خدمات آموزشی 🎓", "بانک نظرات 🔍", "نظرسنجی اساتید ✍️"]

    if user_text == "کانفیگ‌های پرسرعت 🌐":
        await update.message.reply_text("⏳ در حال استخراج کانفیگ‌های تازه و فعال (بدون نیاز به دامنه شخصی)...")
        configs = fetch_latest_configs()
        text = "🌐 **کانفیگ‌های عمومی و پرسرعت امروز:**\n\n" + "\n\n".join([f"🔹 `{c}`" for c in configs]) if configs else "❌ متاسفانه کانفیگ جدیدی یافت نشد."
        await update.message.reply_text(text, parse_mode='Markdown')
        return CHOOSING

    elif user_text == "اخبار 🗞️":
        await update.message.reply_text("⏳ در حال دریافت اخبار لحظه‌ای...")
        news = fetch_news()
        text = "🗞 **آخرین اخبار و اطلاعیه‌ها:**\n\n" + "\n\n".join([f"🔹 {n}" for n in news])
        await update.message.reply_text(text, parse_mode='Markdown')
        return CHOOSING

    elif user_text == "موسیقی و سینما 🎬🎵":
        await update.message.reply_text("🎬🎵 **به بخش موسیقی و سینما خوش آمدید!**\n\nلطفاً دسته‌بندی مورد نظر خود را انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(MUSIC_CAT_KEYBOARD, resize_keyboard=True))
        return MUSIC_CATEGORY

    elif user_text == "سلامت من (AI) ⏱️":
        await update.message.reply_text("🍎 **دستیار هوشمند سلامت و روان**\n\nامروز حالت چطوره؟ (مثلاً: عالیم، خسته‌ام، استرس دارم):", reply_markup=ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True))
        return HEALTH_MOOD

    elif user_text == "ارتباط با ادمین 📞":
        await update.message.reply_text("✍️ پیام خود را برای ادمین بنویسید:\n(اگر سوال مورد نظرتان در بخش‌های دیگر نبود، اینجا مطرح کنید. ادمین در اسرع وقت پاسخ خواهد داد.)", reply_markup=ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True))
        return CONTACT_ADMIN_MSG
        
    elif user_text == "نقشه دانشگاه 🗺️":
        settings = load_db(SETTINGS_DB_FILE)
        photo_id = settings.get("map_photo")
        keyboard = []
        if update.message.from_user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🖼 تنظیم/تغییر عکس نقشه", callback_data="setmapphoto")])
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        if photo_id:
            await update.message.reply_photo(photo=photo_id, caption="📍 نقشه و راهنمای ساختمان‌های دانشگاه آزاد کرج", reply_markup=reply_markup)
        else:
            await update.message.reply_text("📍 عکس نقشه دانشگاه هنوز توسط ادمین ثبت نشده است.", reply_markup=reply_markup)
        return CHOOSING

    elif user_text == "معرفی به دوستان 🚀":
        referral_text = f"🚀 **دانشجوی دانشگاه آزاد کرج هستی و هنوز تو این ربات نیستی؟!** 😱\n\n🔥 این یه ربات ساده نیست! این **سوپراپلیکیشن جامع دانشجویی** ماست که هر چیزی تو دانشگاه نیاز داری رو برات یکجا جمع کرده:\n\n✅ **رادار زنده کلاس‌ها:** چک کن استاد اومده یا کلاس لغوه!\n✅ **بانک نظرات اساتید:** ببین بقیه چه امتیازی به استاد دادن و چطوری نمره میده!\n✅ **گروه‌های درسی و بازارچه:** لینک گروه‌ها و خرید/فروش کتاب.\n✅ **معدل‌گیر پیشرفته و تبدیل عکس به PDF**\n✅ **کانفیگ‌های رایگان و اخبار لحظه‌ای**\n\n👇 **همین الان ربات رو استارت کن!** 👇\n@{context.bot.username}\n\n🌐 **ما را در شبکه‌های اجتماعی دنبال کنید:**\n✈️ **گروه تلگرام اساتید:** [عضویت در گروه تلگرام](https://t.me/Uniazadkaraj_Asatid2)\n🟠 **کانال ایتا:** [عضویت در ایتا](https://eitaa.com/joinchat/2150958289Ccecee59312)\n🟢 **گروه بله:** [عضویت در بله](https://ble.ir/UniAzadKaraj_Asatid)"
        await update.message.reply_text(referral_text, parse_mode='Markdown', disable_web_page_preview=True)
        return CHOOSING

    elif user_text == "معدل‌گیر پیشرفته 🧮":
        context.user_data['gpa_grades'] = []
        await update.message.reply_text("🧮 **ماشین‌حساب معدل**\n\nنمره و تعداد واحد هر درس را با خط تیره بفرستید.\nمثال: نمره 18.5 و 3 واحد 👈 `18.5-3`\n\nهر زمان تمام شد، دکمه «پایان» را بزنید.", parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup([["پایان"]], resize_keyboard=True))
        return GPA_INPUT

    elif user_text == "استخدام 💼":
        await update.message.reply_text("💼 **ثبت رزومه مهارتی**\nمرحله ۱: عنوان تخصص شما دقیقاً چیست؟\n*(مثال: طراح UI/UX، تدوین‌گر ویدیو، ادمین شبکه، برنامه‌نویس پایتون، حسابدار)*", parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True))
        return EMP_TITLE

    elif user_text in needs_major_selection:
        context.user_data["active_section"] = user_text
        await update.message.reply_text(f"📌 **نیم‌سال دوم - بهمن ۱۴۰۴-۱۴۰۵**\n\nشما وارد بخش «{user_text}» شدید.\nلطفاً دانشکده یا رشته کلی خود را انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(MAJORS_KEYBOARD, resize_keyboard=True), parse_mode='Markdown')
        return SELECTING_MAJOR
        
    elif user_text == "پروفایل 👤":
        user_id = str(update.message.from_user.id)
        db = load_db(DB_FILE)
        if user_id in db:
            await update.message.reply_text(f"🪪 **کارت دانشجویی**\nنام: {db[user_id]['name']}\nرشته: {db[user_id]['major']}", parse_mode='Markdown')
        else:
            await update.message.reply_text("نام و نام خانوادگیت رو بفرست:")
            return GETTING_NAME
        return CHOOSING
        
    elif user_text == "📸 عکس به PDF":
        context.user_data["photos"] = []
        await update.message.reply_text("عکس‌ها را بفرست و در نهایت «پایان» را بزن.", reply_markup=ReplyKeyboardMarkup([["📥 پایان و ساخت فایل PDF", "❌ انصراف"]], resize_keyboard=True))
        return COLLECTING_PHOTOS
        
    elif user_text == "پنل ادمین 👑":
        if update.message.from_user.id == ADMIN_ID:
            db = load_db(DB_FILE)
            active_users = "\n".join([f"👤 {u.get('name','')} | @{u.get('username','')} | ⏱ {u.get('last_active','')}" for k, u in list(db.items())[-20:]])
            await update.message.reply_text(f"👑 **پنل مدیریت**\nتعداد کل کاربران: {len(db)}\n\n🟢 **آخرین کاربران فعال:**\n{active_users}")
        else:
            await update.message.reply_text("❌ شما دسترسی به پنل مدیریت ندارید.")
        return CHOOSING

    return CHOOSING

async def calculate_gpa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "پایان":
        grades = context.user_data.get('gpa_grades', [])
        if not grades:
            await update.message.reply_text("داده‌ای وارد نشد.", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
            return CHOOSING
        total_points = sum(g * c for g, c in grades)
        total_credits = sum(c for g, c in grades)
        gpa = total_points / total_credits if total_credits > 0 else 0
        await update.message.reply_text(f"📊 **معدل شما:** `{gpa:.2f}`\nمجموع واحدها: {total_credits}", parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
        return CHOOSING
    
    try:
        grade_str, credit_str = text.split('-')
        grade = float(grade_str.strip())
        credit = float(credit_str.strip())
        context.user_data['gpa_grades'].append((grade, credit))
        await update.message.reply_text("✅ ثبت شد. درس بعدی را بفرستید یا پایان را بزنید.")
    except:
        await update.message.reply_text("❌ فرمت اشتباه است. لطفاً دقیقاً مانند مثال وارد کنید: `17.5-2`", parse_mode='Markdown')
    return GPA_INPUT

async def major_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text
    if user_text == "🔙 بازگشت به منوی اصلی":
        await update.message.reply_text("منوی اصلی 🏠:", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
        return CHOOSING

    context.user_data["active_major"] = user_text
    sub_majors = SUB_MAJORS.get(user_text)
    
    if sub_majors:
        await update.message.reply_text(f"🎓 رشته: {user_text}\nلطفاً گرایش خود را انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(sub_majors, resize_keyboard=True))
        return SELECTING_SUB_MAJOR
    else:
        section = context.user_data.get('active_section')
        if section == "نظرسنجی اساتید ✍️":
            await update.message.reply_text("📝 مرحله ۱: نام استاد؟", reply_markup=ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True))
            return SURVEY_TEACHER
        await update.message.reply_text(f"📌 **نیم‌سال دوم - بهمن ۱۴۰۴-۱۴۰۵**\n\n📍 بخش: {section}\n🎓 رشته: {user_text}", reply_markup=get_action_keyboard(update.message.from_user.id))
        return ACTION_MENU

async def sub_major_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text
    if user_text == "🔙 بازگشت به لیست رشته‌ها":
        await update.message.reply_text("انتخاب رشته:", reply_markup=ReplyKeyboardMarkup(MAJORS_KEYBOARD, resize_keyboard=True))
        return SELECTING_MAJOR
    
    if "(گرایش اصلی)" in user_text:
        full_major = context.user_data.get('active_major')
    else:
        full_major = f"{context.user_data.get('active_major')} - {user_text}"
        
    context.user_data["active_major_full"] = full_major
    section = context.user_data.get("active_section")
    
    if section == "خدمات آموزشی 🎓":
        await update.message.reply_text(f"🎓 رشته: {full_major}\nکدام بخش از خدمات آموزشی؟", reply_markup=ReplyKeyboardMarkup(EDU_SUB_KEYBOARD, resize_keyboard=True))
        return EDU_SERVICES_MENU
        
    elif section == "نظرسنجی اساتید ✍️":
        await update.message.reply_text("📝 مرحله ۱: نام و نام‌خانوادگی استاد؟", reply_markup=ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True))
        return SURVEY_TEACHER
        
    await update.message.reply_text(f"📌 **نیم‌سال دوم - بهمن ۱۴۰۴-۱۴۰۵**\n\n📍 بخش: {section}\n🎓 رشته: {full_major}\nچه کاری می‌خواهید انجام دهید؟", reply_markup=get_action_keyboard(update.message.from_user.id))
    return ACTION_MENU

async def edu_services_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "🔙 بازگشت به منوی اصلی":
        await update.message.reply_text("منوی اصلی 🏠:", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
        return CHOOSING
        
    if text == "🌐 سایت‌های مهم دانشجویی":
        links = (
            "🌐 **سایت‌های مهم و کاربردی دانشگاه:**\n\n"
            "🔹 **سامانه آموزشیار:** [ورود به سایت](https://edu.iau.ir)\n"
            "🔹 **سامانه وادانا (کلاس‌های مجازی):** [ورود به سایت](https://vadana.khuisf.ac.ir)\n"
            "🔹 **سامانه پژوهشیار:** [ورود به سایت](https://ris.iau.ir)\n"
            "🔹 **سامانه ساجد:** [ورود به سایت](https://sajed.iau.ir)"
        )
        await update.message.reply_text(links, parse_mode='Markdown', disable_web_page_preview=True)
        return EDU_SERVICES_MENU

    context.user_data["active_section_edu"] = text
    await update.message.reply_text(f"📌 **نیم‌سال دوم - بهمن ۱۴۰۴-۱۴۰۵**\n\n📍 بخش: {text}", reply_markup=get_action_keyboard(update.message.from_user.id))
    return ACTION_MENU

async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text
    section = context.user_data.get("active_section_edu", context.user_data.get("active_section"))
    major = context.user_data.get("active_major_full", context.user_data.get("active_major", "عمومی"))

    if user_text == "🔙 بازگشت به منوی اصلی":
        context.user_data.pop("active_section_edu", None)
        await update.message.reply_text("منوی اصلی 🏠:", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
        return CHOOSING

    elif user_text == "👀 مشاهده اطلاعات این بخش":
        if section == "بانک نظرات 🔍":
            db = load_db(TEACHERS_DB_FILE)
            major_teachers = db.get(major, {})
            if not major_teachers:
                await update.message.reply_text("هنوز استادی در این رشته ثبت نشده است.", reply_markup=get_action_keyboard(update.message.from_user.id))
                return ACTION_MENU
            
            response = f"📌 **نیم‌سال دوم - بهمن ۱۴۰۴-۱۴۰۵**\n🔍 **بانک نظرات اساتید ({major})**\n\n"
            for t_name, t_data in major_teachers.items():
                avg_score = sum(t_data['scores']) / len(t_data['scores']) if t_data['scores'] else 0
                response += f"👨‍🏫 **{t_name}** | میانگین: ⭐️ {avg_score:.1f}/10\n"
                for rev in t_data['reviews']: response += f" ├ {rev}\n"
                response += " ────────────\n"
            await update.message.reply_text(response, parse_mode='Markdown', reply_markup=get_action_keyboard(update.message.from_user.id))
            return ACTION_MENU
        else:
            db = load_db(CONTENT_DB_FILE)
            data_list = db.get(section, {}).get(major, [])
            if not data_list:
                await update.message.reply_text("محتوایی ثبت نشده. اولین نفر باشید!", reply_markup=get_action_keyboard(update.message.from_user.id))
            else:
                await update.message.reply_text(f"📌 **نیم‌سال دوم - بهمن ۱۴۰۴-۱۴۰۵**\nبخش {section} - {major}:")
                for idx, item in enumerate(data_list):
                    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 حذف این مورد", callback_data=f"del_{section}_{major}_{idx}")]]) if update.message.from_user.id == ADMIN_ID else None
                    await update.message.reply_text(f"🔹 {item}", parse_mode='Markdown', reply_markup=markup)
            return ACTION_MENU

    elif user_text == "➕ ثبت اطلاعات جدید":
        await update.message.reply_text(f"✍️ لطفا پیام خود را برای بخش {section} رشته {major} بنویسید:\n(پیام شما ابتدا برای ادمین ارسال شده و پس از تایید در ربات قرار می‌گیرد)", reply_markup=ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True))
        context.user_data["direct_submit"] = False
        return WAITING_FOR_SUBMISSION

    elif user_text == "⚡️ ثبت مستقیم و فوری (ویژه ادمین)":
        if update.message.from_user.id == ADMIN_ID:
            await update.message.reply_text(f"🚀 **حالت ثبت مستقیم:**\nمطلب خود را برای {section} رشته {major} بنویسید.\n(بدون نیاز به تایید، مستقیماً ثبت و به دانشجویان این رشته اطلاع داده می‌شود!)", reply_markup=ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True))
            context.user_data["direct_submit"] = True
            return WAITING_FOR_SUBMISSION

    return ACTION_MENU

async def receive_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "❌ انصراف": return await cancel(update, context)
    
    section = context.user_data.get("active_section_edu", context.user_data.get("active_section"))
    major = context.user_data.get("active_major_full", context.user_data.get("active_major", "عمومی"))
    user_id = update.message.from_user.id

    if context.user_data.get("direct_submit", False) and user_id == ADMIN_ID:
        db = load_db(CONTENT_DB_FILE)
        if section not in db: db[section] = {}
        if major not in db[section]: db[section][major] = []
        db[section][major].append(text)
        save_db(db, CONTENT_DB_FILE)
        await update.message.reply_text("✅ مطلب مستقیماً ثبت شد!", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
        
        users_db = load_db(DB_FILE)
        for uid, u_info in users_db.items():
            if uid == str(user_id): continue
            u_major = u_info.get("major", "")
            try:
                if section == "اخبار 🗞️" and major == "عمومی":
                    await context.bot.send_message(chat_id=uid, text=f"🚨 **خبر مهم و عمومی دانشگاه:**\n\n{text}")
                elif major in u_major or u_major in major:
                    await context.bot.send_message(chat_id=uid, text=f"📢 **اطلاعیه جدید در بخش {section} رشته شما ({major}):**\n\n{text}")
            except: continue
        return CHOOSING
        
    sub_id = str(uuid.uuid4())[:8]
    pending_submissions[sub_id] = {"user_id": user_id, "section": section, "major": major, "text": text}
    
    keyboard = [[InlineKeyboardButton("✅ تایید انتشار", callback_data=f"approve_{sub_id}"), InlineKeyboardButton("❌ رد کردن", callback_data=f"reject_{sub_id}")]]
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"📩 **درخواست ثبت جدید:**\nبخش: {section}\nرشته: {major}\n\n{text}", reply_markup=InlineKeyboardMarkup(keyboard))
    await update.message.reply_text("✅ با موفقیت ارسال شد و در صورت تایید در ربات قرار می‌گیرد.", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
    return CHOOSING

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "setmapphoto":
        await query.message.reply_text("لطفاً عکس جدید نقشه را ارسال کنید:\n(برای لغو، دکمه انصراف را بزنید)", reply_markup=ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True))
        context.user_data["awaiting_map"] = True
        return WAITING_FOR_MAP_PHOTO
        
    data = query.data.split("_")
    action = data[0]

    if action == "del":
        _, section, major, idx = data
        db = load_db(CONTENT_DB_FILE)
        try:
            del db[section][major][int(idx)]
            save_db(db, CONTENT_DB_FILE)
            await query.edit_message_text(text="🗑 این مورد با موفقیت از دیتابیس ربات حذف شد.")
        except:
            await query.edit_message_text(text="❌ خطا در حذف. ممکن است قبلا حذف شده باشد.")
        return CHOOSING

    if len(data) > 1:
        sub_id = data[1]
        sub = pending_submissions.get(sub_id)
        if not sub:
            await query.edit_message_text(text="❌ منقضی شده یا بررسی شده است.")
            return CHOOSING

        if action == "approve":
            major = sub["major"]
            section = sub.get("section", "")
            if "rating" in sub:
                db = load_db(TEACHERS_DB_FILE)
                if major not in db: db[major] = {}
                if sub["teacher"] not in db[major]: db[major][sub["teacher"]] = {"reviews": [], "scores": []}
                db[major][sub["teacher"]]["reviews"].append(sub["review"])
                db[major][sub["teacher"]]["scores"].append(sub["rating"])
                save_db(db, TEACHERS_DB_FILE)
            else:
                db = load_db(CONTENT_DB_FILE)
                if section not in db: db[section] = {}
                if major not in db[section]: db[section][major] = []
                db[section][major].append(sub["text"])
                save_db(db, CONTENT_DB_FILE)
                
            await query.edit_message_text(text="✅ تایید و در ربات منتشر شد.")
            try:
                if str(sub["user_id"]) != str(ADMIN_ID):
                    await context.bot.send_message(chat_id=sub["user_id"], text="🎉 تبریک! اطلاعات ارسالی شما تایید و در ربات منتشر شد!")
            except: pass
            
            users_db = load_db(DB_FILE)
            for uid, u_info in users_db.items():
                if uid == str(sub["user_id"]): continue
                u_major = u_info.get("major", "")
                try:
                    if section == "اخبار 🗞️" and major == "عمومی":
                        await context.bot.send_message(chat_id=uid, text=f"🚨 **خبر مهم و عمومی دانشگاه:**\n\n{sub['text']}")
                    elif major in u_major or u_major in major:
                        await context.bot.send_message(chat_id=uid, text=f"📢 **اطلاعیه جدید در بخش {section} رشته شما ({major}):**\n\n{sub['text']}")
                except: continue

        elif action == "reject":
            await query.edit_message_text(text="❌ رد شد.")
            try:
                if str(sub["user_id"]) != str(ADMIN_ID):
                    await context.bot.send_message(chat_id=sub["user_id"], text="متاسفانه اطلاعات ارسالی شما تایید نشد.")
            except: pass
        del pending_submissions[sub_id]
    return CHOOSING

async def receive_map_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ انصراف": 
        return await cancel(update, context)
        
    if update.message.from_user.id == ADMIN_ID and context.user_data.get("awaiting_map"):
        photo_id = update.message.photo[-1].file_id
        settings = load_db(SETTINGS_DB_FILE)
        settings["map_photo"] = photo_id
        save_db(settings, SETTINGS_DB_FILE)
        context.user_data["awaiting_map"] = False
        await update.message.reply_text("✅ عکس نقشه با موفقیت در سیستم ثبت شد و برای همه دانشجویان قابل مشاهده است.", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
    return CHOOSING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ عملیات لغو شد.", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
    return CHOOSING

async def health_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['h_mood'] = update.message.text
    await update.message.reply_text("عالی! حالا برای محاسبه دقیق‌تر، قد خود را به سانتیمتر وارد کنید (مثال: 175):")
    return HEALTH_HEIGHT

async def health_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    try:
        context.user_data['h_height'] = float(update.message.text)
        await update.message.reply_text("وزن خود را به کیلوگرم وارد کنید (مثال: 70):")
        return HEALTH_WEIGHT
    except:
        await update.message.reply_text("لطفاً فقط عدد وارد کنید:")
        return HEALTH_HEIGHT

async def health_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    try:
        w = float(update.message.text)
        h = context.user_data['h_height'] / 100
        bmi = w / (h * h)
        water = int(w * 35)
        mood = context.user_data.get('h_mood', '')
        
        advice = f"💡 **نکته روانشناسی:** با توجه به اینکه گفتی «{mood}»، یادت باشه استراحت بین درس‌ها و قدم زدن کوتاه می‌تونه خیلی به بازدهی ذهنت کمک کنه."
        await update.message.reply_text(f"📊 **تحلیل سلامت شما:**\n\n⚖️ شاخص توده بدنی (BMI): {bmi:.1f}\n💧 پیشنهاد مصرف آب: {water} میلی‌لیتر در روز (حدود {int(water/250)} لیوان)\n\n{advice}", parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
        return CHOOSING
    except:
        await update.message.reply_text("لطفاً فقط عدد وارد کنید:")
        return HEALTH_WEIGHT

async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ انصراف": return await cancel(update, context)
    user = update.message.from_user
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"📩 **پیام به ادمین:**\nاز: {user.first_name} (@{user.username} | {user.id})\n\nمتن: {text}")
    await update.message.reply_text("✅ پیام شما با موفقیت به ادمین ارسال شد.", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
    return CHOOSING

async def emp_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['emp_title'] = update.message.text
    await update.message.reply_text(f"مرحله ۲: عالی! حالا به من بگو مهارت‌ها و سوابق اجراییت در زمینه «{update.message.text}» دقیقاً چیه؟\n*(مثلاً: تسلط به پایتون، سابقه کار در تیم گرافیک، فن بیان قوی)*", parse_mode='Markdown')
    return EMP_SKILLS

async def emp_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['emp_skills'] = update.message.text
    await update.message.reply_text("مرحله ۳: تجربه کاری شما چقدره؟\n*(به سال یا ماه بنویس)*", parse_mode='Markdown')
    return EMP_LEVEL

async def emp_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['emp_level'] = update.message.text
    await update.message.reply_text("مرحله آخر: راه‌های ارتباطی برای کارفرما رو اینجا بنویس:\n*(آیدی تلگرام، ایمیل، یا شماره تماس)*", parse_mode='Markdown')
    return EMP_CONTACT

async def emp_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    text = f"💼 **رزومه جدید برای استخدام**\n\n🎯 تخصص: {context.user_data['emp_title']}\n🛠 مهارت و سوابق: {context.user_data['emp_skills']}\n📈 تجربه کاری: {context.user_data['emp_level']}\n📞 ارتباط: {update.message.text}"
    sub_id = str(uuid.uuid4())[:8]
    pending_submissions[sub_id] = {"type": "content", "section": "استخدام 💼", "major": "عمومی", "text": text, "user_id": update.message.from_user.id}
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"📩 {text}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تایید انتشار", callback_data=f"approve_{sub_id}"), InlineKeyboardButton("❌ رد رزومه", callback_data=f"reject_{sub_id}")]]))
    await update.message.reply_text("✅ رزومه شما به شکلی حرفه‌ای تنظیم و جهت تایید ارسال شد.", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
    return CHOOSING

async def srv_teacher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['s_teach'] = update.message.text
    await update.message.reply_text("مرحله ۲: نام درس چه بود؟")
    return SURVEY_COURSE

async def srv_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['s_course'] = update.message.text
    await update.message.reply_text("مرحله ۳: اخلاق و رفتار با دانشجو چطور بود؟")
    return SURVEY_BEHAVIOR

async def srv_behavior(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['s_beh'] = update.message.text
    await update.message.reply_text("مرحله ۴: وضعیت حضور و غیاب؟")
    return SURVEY_ATTENDANCE

async def srv_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['s_att'] = update.message.text
    await update.message.reply_text("مرحله ۵: نمره‌دهی پایان ترم؟")
    return SURVEY_GRADING

async def srv_grading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['s_grd'] = update.message.text
    await update.message.reply_text("مرحله ۶: منبع مطالعه (جزوه یا کتاب)؟")
    return SURVEY_MATERIAL

async def srv_material(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['s_mat'] = update.message.text
    await update.message.reply_text("مرحله ۷ (آخر): در کل، از ۱ تا ۱۰ چه امتیازی به این استاد می‌دهید؟ (فقط یک عدد وارد کنید)")
    return SURVEY_RATING

async def srv_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    try:
        rating = float(update.message.text)
        if not (1 <= rating <= 10): raise Exception
    except:
        await update.message.reply_text("لطفاً یک عدد معتبر بین ۱ تا ۱۰ وارد کنید:")
        return SURVEY_RATING
    
    t_name = context.user_data['s_teach']
    major = context.user_data.get("active_major_full", context.user_data.get("active_major", "عمومی"))
    review_text = (f"👨‍🏫 استاد: {t_name} | امتیاز: {rating}\n"
                   f"درس: {context.user_data['s_course']}\n"
                   f"اخلاق: {context.user_data['s_beh']} | حضورغیاب: {context.user_data['s_att']}\n"
                   f"نمره: {context.user_data['s_grd']} | منبع: {context.user_data['s_mat']}")
    
    sub_id = str(uuid.uuid4())[:8]
    pending_submissions[sub_id] = {"type": "survey", "teacher": t_name, "major": major, "review": review_text, "rating": rating, "user_id": update.message.from_user.id}
    
    keyboard = [[InlineKeyboardButton("✅ تایید انتشار", callback_data=f"approve_{sub_id}"), InlineKeyboardButton("❌ رد کردن", callback_data=f"reject_{sub_id}")]]
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"📩 **نظر جدید برای استاد:**\nرشته: {major}\n\n{review_text}", reply_markup=InlineKeyboardMarkup(keyboard))
    await update.message.reply_text("✅ فرم شما ثبت و برای تایید ارسال شد.", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
    return CHOOSING

async def music_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 بازگشت به منوی اصلی": return await start(update, context)
    context.user_data['m_cat'] = text
    await update.message.reply_text(f"شما بخش {text} را انتخاب کردید.\n\nنام اثر (آهنگ، فیلم یا سریال) رو بنویس:", reply_markup=ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True))
    return MUSIC_TITLE

async def music_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['m_title'] = update.message.text
    await update.message.reply_text("یک تحلیل، نقد یا بررسی حرفه‌ای از این اثر بنویس:\n*(مثلاً درباره کارگردانی، بازیگری، آهنگسازی، کیفیت وکال، یا حسی که بهت داده)*", parse_mode='Markdown')
    return MUSIC_REVIEW

async def music_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    context.user_data['m_review'] = update.message.text
    await update.message.reply_text("در نهایت از ۱ تا ۱۰ چه امتیازی بهش می‌دی؟ (فقط یک عدد)")
    return MUSIC_RATING

async def music_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    try:
        rating = float(update.message.text)
        if not (1 <= rating <= 10): raise Exception
    except:
        await update.message.reply_text("لطفاً یک عدد معتبر بین ۱ تا ۱۰ وارد کنید:")
        return MUSIC_RATING
        
    text = f"🎨 **تحلیل {context.user_data['m_cat']}**\n🎬 اثر: {context.user_data['m_title']}\n✍️ نقد: {context.user_data['m_review']}\n⭐️ امتیاز کاربر: {rating}/10"
    sub_id = str(uuid.uuid4())[:8]
    pending_submissions[sub_id] = {"type": "content", "section": "موسیقی و سینما 🎬🎵", "major": "عمومی", "text": text, "user_id": update.message.from_user.id}
    
    keyboard = [[InlineKeyboardButton("✅ تایید انتشار", callback_data=f"approve_{sub_id}"), InlineKeyboardButton("❌ رد", callback_data=f"reject_{sub_id}")]]
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"📩 **تحلیل هنری جدید:**\n\n{text}", reply_markup=InlineKeyboardMarkup(keyboard))
    await update.message.reply_text("✅ تحلیل زیبای شما ثبت و برای تایید ارسال شد.", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
    return CHOOSING

async def save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['temp_name'] = update.message.text
    await update.message.reply_text("رشته خود را بنویسید:")
    return GETTING_USER_MAJOR

async def save_user_major(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db(DB_FILE)
    db[str(update.message.from_user.id)] = {"name": context.user_data.get('temp_name', ''), "major": update.message.text}
    save_db(db, DB_FILE)
    await update.message.reply_text("✅ پروفایل شما با موفقیت ساخته شد!", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
    return CHOOSING

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    chat_id = update.message.chat_id
    photo_file = await update.message.photo[-1].get_file()
    file_path = os.path.join(TEMP_DIR, f"{chat_id}_{len(context.user_data.get('photos', []))}.jpg")
    await photo_file.download_to_drive(file_path)
    context.user_data.setdefault("photos", []).append(file_path)
    await update.message.reply_text("📸 عکس دریافت شد. اگر عکس دیگری دارید بفرستید یا دکمه «پایان» را بزنید.")
    return COLLECTING_PHOTOS

async def create_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف":
        photo_paths = context.user_data.get("photos", [])
        for p in photo_paths:
            if os.path.exists(p): os.remove(p)
        return await cancel(update, context)
        
    photo_paths = context.user_data.get("photos", [])
    if photo_paths:
        await update.message.reply_text("⏳ در حال پردازش و ساخت فایل PDF...")
        try:
            image_list = [Image.open(p).convert('RGB') for p in photo_paths]
            pdf_path = os.path.join(TEMP_DIR, "Jozveh.pdf")
            image_list[0].save(pdf_path, save_all=True, append_images=image_list[1:])
            with open(pdf_path, "rb") as f: 
                await update.message.reply_document(document=f, filename="Jozveh.pdf", caption="🚀 بفرما اینم فایل PDF!", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
        except:
            await update.message.reply_text("❌ متاسفانه خطایی در ساخت PDF رخ داد.", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
        for p in photo_paths:
            if os.path.exists(p): os.remove(p)
    else:
        await update.message.reply_text("شما عکسی ارسال نکردید.", reply_markup=ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True))
    return CHOOSING

def main() -> None:
    keep_alive()
    # 🔴 اینجا توکن از متغیرهای محیطی لیارا گرفته میشه
    TOKEN = os.environ.get("BOT_TOKEN", "8492988670:AAG6eDKGjsPcPuFxaEuW5P3xUUylwc4pLzc")
    
    if not TOKEN:
        logger.error("BOT_TOKEN is not set!")
        return
    
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start), 
            CommandHandler("fetch_channel", fetch_channel_cmd), 
            CallbackQueryHandler(admin_callback, pattern="^setmapphoto$|^del_|^approve_|^reject_"),
            CallbackQueryHandler(verify_join_callback, pattern="^verify_join$")
        ],
        states={
            CHOOSING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler), 
                CallbackQueryHandler(admin_callback, pattern="^setmapphoto$|^del_|^approve_|^reject_"),
                CallbackQueryHandler(verify_join_callback, pattern="^verify_join$")
            ],
            SELECTING_MAJOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, major_selected)],
            SELECTING_SUB_MAJOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, sub_major_selected)],
            ACTION_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, action_handler), 
                CallbackQueryHandler(admin_callback, pattern="^setmapphoto$|^del_|^approve_|^reject_")
            ],
            EDU_SERVICES_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, edu_services_handler)],
            WAITING_FOR_SUBMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_submission)],
            SURVEY_TEACHER: [MessageHandler(filters.TEXT, srv_teacher)],
            SURVEY_COURSE: [MessageHandler(filters.TEXT, srv_course)],
            SURVEY_BEHAVIOR: [MessageHandler(filters.TEXT, srv_behavior)],
            SURVEY_ATTENDANCE: [MessageHandler(filters.TEXT, srv_attendance)],
            SURVEY_GRADING: [MessageHandler(filters.TEXT, srv_grading)],
            SURVEY_MATERIAL: [MessageHandler(filters.TEXT, srv_material)],
            SURVEY_RATING: [MessageHandler(filters.TEXT, srv_rating)],
            EMP_TITLE: [MessageHandler(filters.TEXT, emp_title)],
            EMP_SKILLS: [MessageHandler(filters.TEXT, emp_skills)],
            EMP_LEVEL: [MessageHandler(filters.TEXT, emp_level)],
            EMP_CONTACT: [MessageHandler(filters.TEXT, emp_contact)],
            GPA_INPUT: [MessageHandler(filters.TEXT, calculate_gpa)],
            GETTING_NAME: [MessageHandler(filters.TEXT, save_name)],
            GETTING_USER_MAJOR: [MessageHandler(filters.TEXT, save_user_major)],
            COLLECTING_PHOTOS: [
                MessageHandler(filters.PHOTO, receive_photo), 
                MessageHandler(filters.Text("📥 پایان و ساخت فایل PDF") | filters.Text("❌ انصراف"), create_pdf)
            ],
            WAITING_FOR_MAP_PHOTO: [
                MessageHandler(filters.PHOTO | filters.TEXT, receive_map_photo), 
                CallbackQueryHandler(admin_callback, pattern="^setmapphoto$|^del_|^approve_|^reject_")
            ],
            HEALTH_MOOD: [MessageHandler(filters.TEXT, health_mood)],
            HEALTH_HEIGHT: [MessageHandler(filters.TEXT, health_height)],
            HEALTH_WEIGHT: [MessageHandler(filters.TEXT, health_weight)],
            CONTACT_ADMIN_MSG: [MessageHandler(filters.TEXT, contact_admin)],
            MUSIC_CATEGORY: [MessageHandler(filters.TEXT, music_category)],
            MUSIC_TITLE: [MessageHandler(filters.TEXT, music_title)],
            MUSIC_REVIEW: [MessageHandler(filters.TEXT, music_review)],
            MUSIC_RATING: [MessageHandler(filters.TEXT, music_rating)]
        },
        fallbacks=[
            CommandHandler("start", start), 
            CommandHandler("fetch_channel", fetch_channel_cmd), 
            CallbackQueryHandler(admin_callback, pattern="^setmapphoto$|^del_|^approve_|^reject_"),
            MessageHandler(filters.Regex("^❌ انصراف$"), cancel)
        ],
    )
    
    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
