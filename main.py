import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
import time
import os
import threading
import requests
import hashlib

# --- إعدادات البوت ---
BOT_TOKEN = "8678728270:AAEhK-Vb7Sbnksfl8OUFGcOCm3C2yQ8WbWo"
bot = telebot.TeleBot(BOT_TOKEN)

user_sessions = {}

def get_user_data(chat_id):
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            'driver': None,
            'is_logged_in': False,
            'is_scraping': False,
            'search_mode': '', 
            'target_input': '', 
            'count': 0,
            'temp_login': '',
            'sent_images_hashes': set()
        }
    return user_sessions[chat_id]

# --- إعداد المتصفح ---
def init_driver(chat_id):
    data = get_user_data(chat_id)
    if data['driver'] is None:
        chrome_options = Options()
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            data['driver'] = driver
        except Exception as e:
            print(f"Error: {e}")
            return None
    return data['driver']

# --- لوحة المفاتيح ---
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add(KeyboardButton("🚀 تشغيل البوت وفتح جوجل"))
    keyboard.add(KeyboardButton("🔍 بحث وجمع الصور"), KeyboardButton("👤 سحب من حساب"))
    keyboard.add(KeyboardButton("إيقاف العملية 🛑"), KeyboardButton("حالة البوت 👤"))
    return keyboard

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(
        message.chat.id, 
        "مرحبًا 👋 ! أنا بوت جمع الصور من Pinterest اختر العملية التي تريدها للبدء .", 
        reply_markup=get_main_keyboard()
    )

# --- نظام تسجيل الدخول ---
@bot.message_handler(func=lambda message: message.text == "🚀 تشغيل البوت وفتح جوجل")
def handle_google_start(message):
    chat_id = message.chat.id
    driver = init_driver(chat_id)
    bot.send_message(chat_id, "🌐 جاري فتح جوجل...")
    driver.get("https://www.google.com")
    msg = bot.send_message(chat_id, "📧 أرسل الإيميل أو الهاتف الخاص ببنترست:")
    bot.register_next_step_handler(msg, process_login_id)

def process_login_id(message):
    get_user_data(message.chat.id)['temp_login'] = message.text
    msg = bot.send_message(message.chat.id, "🔑 أرسل كلمة المرور:")
    bot.register_next_step_handler(msg, login_execution)

def login_execution(message):
    chat_id = message.chat.id
    data = get_user_data(chat_id)
    password = message.text
    login_id = data['temp_login']
    threading.Thread(target=login_logic, args=(chat_id, login_id, password)).start()

def login_logic(chat_id, login_id, password):
    data = get_user_data(chat_id)
    driver = data['driver']
    try:
        driver.get("https://www.pinterest.com/login/")
        wait = WebDriverWait(driver, 15)
        email_field = wait.until(EC.element_to_be_clickable((By.ID, "email")))
        email_field.send_keys(login_id)
        pass_field = driver.find_element(By.ID, "password")
        pass_field.send_keys(password)
        pass_field.send_keys(Keys.ENTER)
        time.sleep(5)
        data['is_logged_in'] = True
        bot.send_message(chat_id, "تم تسجيل الدخول وحفظ الجلسة بنجاح! ✅")
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ خطأ: {str(e)}")

@bot.message_handler(func=lambda message: message.text in ["🔍 بحث وجمع الصور", "👤 سحب من حساب"])
def unified_handler(message):
    chat_id = message.chat.id
    data = get_user_data(chat_id)
    if not data['is_logged_in']: return bot.send_message(chat_id, "❌ سجل الدخول أولاً!")
    data['search_mode'] = 'text' if "بحث" in message.text else 'profile'
    msg = bot.send_message(chat_id, "📌 أرسل كلمة البحث أو رابط الحساب:")
    bot.register_next_step_handler(msg, process_target_input)

def process_target_input(message):
    get_user_data(message.chat.id)['target_input'] = message.text
    msg = bot.send_message(message.chat.id, "🔢 العدد المطلوب:")
    bot.register_next_step_handler(msg, process_count)

def process_count(message):
    chat_id = message.chat.id
    
    if not message.text.isdigit():
        return bot.send_message(chat_id, "❌ أرسل رقماً فقط.")
    
    data = get_user_data(chat_id)
    data['count'] = int(message.text)
    data['is_scraping'] = True

    # 👇 الرسالة هنا في المكان الصح
    bot.send_message(chat_id, "⚡️ جارٍ تنفيذ الطلب...")

    threading.Thread(target=universal_engine, args=(chat_id,)).start()

# ==========================================
# المحرك الجديد المطور (لوب ديناميكي لضمان العدد)
# ==========================================
def universal_engine(chat_id):
    data = get_user_data(chat_id)
    driver = data['driver']
    target = data['count']
    mode = data['search_mode']
    
    try:
        # التوجه للرابط
        if mode == 'text':
            driver.get(f"https://www.pinterest.com/search/pins/?q={data['target_input']}")
        else:
            url = data['target_input']
            if "pinterest.com" not in url: url = f"https://www.pinterest.com/{url.strip('@')}/"
            driver.get(url)
        
        time.sleep(5)
        
        sent_count = 0
        seen_links = set()
        no_new_count = 0

        # دالة المعالجة الداخلية الآمنة (لا ترفع العداد إلا بالنجاح التام)
        def process_single_link(link, is_retry=False):
            nonlocal sent_count
            try:
                driver.execute_script(f"window.open('{link}', '_blank');")
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(1)
                
                is_video = False
                try:
                    if driver.find_elements(By.TAG_NAME, "video"):
                        is_video = True
                    else:
                        media_elements = driver.find_elements(By.XPATH, "//*[@src]")
                        for el in media_elements:
                            src = el.get_attribute("src")
                            if src and (".mp4" in src.lower() or ".m3u8" in src.lower()):
                                is_video = True
                                break
                except Exception:
                    pass
                
                if is_video:
                    return "video"
                
                wait = WebDriverWait(driver, 10)
                img_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='originals'], img[src*='736x'], img[src*='564x']")))
                img_url = img_element.get_attribute("src")
                if not img_url:
                    return "fail"
                    
                hd_url = img_url.replace("/236x/", "/originals/").replace("/474x/", "/originals/").replace("/564x/", "/originals/").replace("/736x/", "/originals/")
                
                resp = requests.get(hd_url, timeout=15)
                if resp.status_code == 200:
                    img_data = resp.content
                    img_hash = hashlib.md5(img_data).hexdigest()
                    
                    if img_hash not in data['sent_images_hashes']:
                        temp_path = f"img_{chat_id}_{sent_count}.jpg"
                        with open(temp_path, "wb") as f: f.write(img_data)
                        
                        caption_text = f"✅ ({sent_count+1}/{target})"
                        if is_retry: caption_text += " (إعادة محاولة)"
                            
                        # حماية صارمة لإرسال التليجرام
                        try:
                            with open(temp_path, "rb") as photo:
                                bot.send_photo(chat_id, photo, caption=caption_text)
                        except Exception as telegram_err:
                            if os.path.exists(temp_path): os.remove(temp_path)
                            return "fail" # فشل الإرسال، لم يتم رفع العداد
                            
                        if os.path.exists(temp_path): os.remove(temp_path)
                        data['sent_images_hashes'].add(img_hash)
                        sent_count += 1 # رفع العداد هنا فقط
                        return "success"
                    else:
                        return "duplicate"
                else:
                    return "fail"
                    
            except Exception:
                return "fail"
            finally:
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                time.sleep(0.8)

        # اللوب الخارجي: لا يغلق حتى يكتمل العدد المطلوب (sent_count == target)
        while sent_count < target and data['is_scraping']:
            needed_count = target - sent_count
            collected_links = []
            
            # --- المرحلة 1: الجمع (لسد النقص) ---
            while len(collected_links) < needed_count and data['is_scraping']:
                try:
                    elements = driver.find_elements(By.XPATH, "//div[@data-test-id='pin']//a")
                    new_found = False
                    for el in elements:
                        try:
                            link = el.get_attribute("href")
                            if link and "/pin/" in link and link not in seen_links:
                                seen_links.add(link)
                                collected_links.append(link)
                                new_found = True
                                if len(collected_links) >= needed_count: 
                                    break
                        except StaleElementReferenceException: 
                            continue
                    
                    if not new_found:
                        no_new_count += 1
                    else:
                        no_new_count = 0
                    
                    if no_new_count > 8:
                        break # نزل لآخر الصفحة ولا يوجد جديد
                    
                    driver.execute_script("window.scrollBy(0, 800);")
                    time.sleep(1.5)
                    
                except Exception:
                    time.sleep(1)
                    continue

            if not data['is_scraping']: return
            
            # إذا وصلنا للنهاية المطلقة ولم نجد أي روابط جديدة نهائياً (غالباً في حساب فارغ)
            if not collected_links:
                break 
            failed_links = []

            # --- المرحلة 2: المعالجة ---
            for link in collected_links:
                if not data['is_scraping'] or sent_count >= target: break
                
                result = process_single_link(link)
                if result == "fail":
                    failed_links.append(link)
                elif result in ["video", "duplicate"]:
                    continue # التخطي الطبيعي

            # --- المرحلة 3: نظام إعادة المحاولة (3 محاولات) ---
            max_retries = 3
            for attempt in range(max_retries):
                if not data['is_scraping'] or sent_count >= target or not failed_links:
                    break
                current_failed = failed_links.copy()
                failed_links = []
                
                for link in current_failed:
                    if not data['is_scraping'] or sent_count >= target: break
                    
                    result = process_single_link(link, is_retry=True)
                    if result == "fail":
                        failed_links.append(link)

            # إنهاء في حال الحسابات لو انتهى المحتوى تماماً ومازال العدد ناقصاً
            if mode == 'profile' and no_new_count > 8 and sent_count < target:
                bot.send_message(chat_id, "⚠️ وصلنا لنهاية الحساب تماماً ولا توجد صور إضافية يمكن سحبها.")
                break

        # الخاتمة النهائية (بعد كسر اللوب الخارجي)
        if sent_count == target:
            bot.send_message(chat_id, f"🏁 اكتملت المهمة بنجاح ! تم إرسال {sent_count} صورة 💯 .")
        else:
            bot.send_message(chat_id, f"🏁 توقفت العملية. تم إرسال {sent_count} صورة من أصل {target} المطلوبة (السبب: نفاد المحتوى تماماً من المصدر).")

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ حدث خطأ غير متوقع، لكن البوت مستمر في العمل: {str(e)}")
    finally:
        data['is_scraping'] = False

@bot.message_handler(func=lambda message: message.text == "إيقاف العملية 🛑")
def stop(message):
    get_user_data(message.chat.id)['is_scraping'] = False
    bot.send_message(message.chat.id, "🛑 سيتم التوقف فور إنهاء المعالجة الحالية...")

@bot.message_handler(func=lambda message: message.text == "حالة البوت 👤")
def status(message):
    data = get_user_data(message.chat.id)
    status_txt = "يعمل ⚙️" if data['is_scraping'] else "متوقف 💤"
    bot.send_message(message.chat.id, f"👤 حالة البوت: {status_txt}\n🖼️ صور فريدة مرسلة: {len(data['sent_images_hashes'])}")

if __name__ == "__main__":
    print("Bot is starting...")
    bot.infinity_polling()
