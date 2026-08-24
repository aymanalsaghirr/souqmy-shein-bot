import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from playwright.sync_api import sync_playwright
from flask import Flask
import threading

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running on Render!"

def run_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ضع التوكن الخاص بك هنا
TOKEN = "8871899951:AAGcoT8IQwY2DLWKKwePQ8weNFVa-oxDcgM"
bot = telebot.TeleBot(TOKEN)

# قاموس لتخزين روابط المستخدمين مؤقتاً لحل مشكلة طول الرابط
user_data = {}

def calculate_price_logic(black_price, red_price=None):
    if not red_price or red_price >= black_price:
        return f"السعر الأساسي: {black_price} SAR"
    
    discount = ((black_price - red_price) / black_price) * 100
    
    if discount <= 5.0:
        return f"السعر الأصلي: {black_price} SAR\nالسعر بعد الخصم ({discount:.0f}%): {red_price} SAR"
    else:
        return f"السعر المعتمد: {black_price} SAR (بدون كوبونات/خصم إضافي)"

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    
    if "shein" in url:
        # ضمان توجيه الرابط تلقائياً للمتجر السعودي إذا كان رابطاً عاماً
        if "sa.shein.com" not in url and "ar.shein.com" not in url:
            url = url.replace("www.shein.com", "sa.shein.com").replace("m.shein.com", "sa.shein.com")
            
        user_data[message.chat.id] = url
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("💰 جلب السعر والمقاسات", callback_data="price"))
        markup.row(InlineKeyboardButton("📸 التقاط صورة (Screenshot)", callback_data="screen"))
        markup.row(InlineKeyboardButton("🖼️ سحب الصور بشعار سوقمي", callback_data="images"))
        markup.row(InlineKeyboardButton("🛒 استخراج بيانات السلة", callback_data="cart"))
        
        bot.reply_to(message, "مرحباً بك في نظام تسعير سوقمي (السعودية 🇸🇦)\nاختر العملية المطلوبة للرابط:", reply_markup=markup)
    else:
        bot.reply_to(message, "يرجى إرسال رابط صحيح من شي إن.")

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    action = call.data
    chat_id = call.message.chat.id
    
    url = user_data.get(chat_id)
    if not url:
        bot.answer_callback_query(call.id, "❌ عذراً، يرجى إرسال الرابط مجدداً.")
        return

    bot.answer_callback_query(call.id, "⏳ جاري المعالجة...")
    msg = bot.send_message(chat_id, "⏳ جاري تشغيل المتصفح وسحب البيانات من السعودية...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            # 📱 إعداد المتصفح ليعمل كـ "هاتف آيفون" تماماً (موبايل فيو) لتجنب الشاشة العريضة والفراغات البيضاء
            context = browser.new_context(
                viewport={'width': 390, 'height': 844},
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                locale='ar-SA',
                geolocation={'latitude': 24.7136, 'longitude': 46.6753}, 
                permissions=['geolocation'],
                is_mobile=True,
                has_touch=True
            )
            page = context.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_load_state('networkidle')

            if action == "price":
                try:
                    black_price_text = page.locator('.original-price').inner_text() 
                    red_price_text = page.locator('.discount-price').inner_text() 
                    
                    black_price = float(black_price_text.replace('SAR', '').strip())
                    red_price = float(red_price_text.replace('SAR', '').strip())
                    
                    final_text = calculate_price_logic(black_price, red_price)
                except:
                    final_text = "السعر الأساسي: لم يتم تحديد الهيكل بعد (تحتاج ضبط Selectors لاحقاً)"

                bot.edit_message_text(f"✅ النتائج:\n\n{final_text}", chat_id=chat_id, message_id=msg.message_id)

            elif action == "screen":
                # الانتظار 5 ثوانٍ لضمان تحميل صور شي إن بداخل شاشة الجوال
                page.wait_for_timeout(5000)
                
                screenshot_path = "product.png"
                # التقاط الشاشة الظاهرة فقط (الشاشة الرئيسية للمنتج) بدون مساحات بيضاء وبمقاس هاتف
                page.screenshot(path=screenshot_path, full_page=False)

                with open(screenshot_path, 'rb') as photo:
                    bot.send_photo(chat_id, photo, caption="📸 صورة المنتج (تصميم جوال) من سوقمي 🇸🇦")
                bot.delete_message(chat_id, msg.message_id)
            
            elif action == "images":
                 bot.edit_message_text("جاري سحب الصور وإضافة الهوية البصرية...", chat_id=chat_id, message_id=msg.message_id)
            
            elif action == "cart":
                 bot.edit_message_text("🛒 قريباً: ميزة سحب السلة...", chat_id=chat_id, message_id=msg.message_id)

            browser.close()
            
    except Exception as e:
        bot.edit_message_text(f"❌ حدث خطأ: {str(e)}", chat_id=chat_id, message_id=msg.message_id)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    print("Bot is running...")
    bot.remove_webhook()
    bot.infinity_polling()
