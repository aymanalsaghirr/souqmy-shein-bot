import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from playwright.sync_api import sync_playwright
from flask import Flask
import threading

# --- إعداد الخادم الوهمي لإرضاء منصة Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running on Render!"

def run_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
# ----------------------------------------------

# ضع التوكن الجديد هنا بعد تغييره في BotFather
TOKEN = "8871899951:AAHl7umC0vzRbwsu4bWs3Dmejlv5tP7jl9g"
bot = telebot.TeleBot(TOKEN)

# دالة المنطق الرياضي لحساب السعر
def calculate_price_logic(black_price, red_price=None):
    if not red_price or red_price >= black_price:
        return f"السعر الأساسي: {black_price} SAR"
    
    # حساب نسبة الخصم
    discount = ((black_price - red_price) / black_price) * 100
    
    # إذا كان الخصم 5% أو أقل، نظهر السعرين
    if discount <= 5.0:
        return f"السعر الأصلي: {black_price} SAR\nالسعر بعد الخصم ({discount:.0f}%): {red_price} SAR"
    else:
        # إذا الخصم أكبر من 5%، نتجاهل الأحمر ونعرض الأسود فقط
        return f"السعر المعتمد: {black_price} SAR (بدون كوبونات/خصم إضافي)"

# استقبال الروابط وعرض الخيارات
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    
    if "shein" in url:
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("💰 جلب السعر والمقاسات", callback_data=f"price|{url}"))
        markup.row(InlineKeyboardButton("📸 التقاط صورة (Screenshot)", callback_data=f"screen|{url}"))
        markup.row(InlineKeyboardButton("🖼️ سحب الصور بشعار سوقمي", callback_data=f"images|{url}"))
        markup.row(InlineKeyboardButton("🛒 استخراج بيانات السلة", callback_data=f"cart|{url}"))
        
        bot.reply_to(message, "مرحباً بك في نظام تسعير سوقمي! 🚀\nاختر العملية المطلوبة للرابط:", reply_markup=markup)
    else:
        bot.reply_to(message, "يرجى إرسال رابط صحيح من شي إن.")

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    action, url = call.data.split("|", 1)
    
    bot.answer_callback_query(call.id, "⏳ جاري المعالجة...")
    msg = bot.send_message(call.message.chat.id, "⏳ جاري تشغيل المتصفح وسحب البيانات من السعودية...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                locale='ar-SA',
                geolocation={'latitude': 24.7136, 'longitude': 46.6753}, 
                permissions=['geolocation']
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

                bot.edit_message_text(f"✅ النتائج:\n\n{final_text}", chat_id=call.message.chat.id, message_id=msg.message_id)

            elif action == "screen":
                screenshot_path = "product.png"
                page.screenshot(path=screenshot_path)
                with open(screenshot_path, 'rb') as photo:
                    bot.send_photo(call.message.chat.id, photo, caption="📸 لقطة شاشة للمنتج")
                bot.delete_message(call.message.chat.id, msg.message_id)
            
            elif action == "images":
                 bot.edit_message_text("جاري سحب الصور وإضافة الهوية البصرية...", chat_id=call.message.chat.id, message_id=msg.message_id)
            
            elif action == "cart":
                 bot.edit_message_text("🛒 قريباً: ميزة سحب السلة...", chat_id=call.message.chat.id, message_id=msg.message_id)

            browser.close()
            
    except Exception as e:
        bot.edit_message_text(f"❌ حدث خطأ: {str(e)}", chat_id=call.message.chat.id, message_id=msg.message_id)

if __name__ == "__main__":
    # تشغيل الخادم الوهمي في مسار منفصل
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    
    # تشغيل البوت
    print("Bot is running...")
    bot.infinity_polling()
