import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from playwright.sync_api import sync_playwright
from PIL import Image
from io import BytesIO
import requests

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

# معالجة ضغطات الأزرار
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    action, url = call.data.split("|", 1)
    
    bot.answer_callback_query(call.id, "⏳ جاري المعالجة...")
    msg = bot.send_message(call.message.chat.id, "⏳ جاري تشغيل المتصفح وسحب البيانات من السعودية...")

    try:
        with sync_playwright() as p:
            # تشغيل متصفح مخفي
            browser = p.chromium.launch(headless=True)
            # تعيين الموقع للسعودية لضمان عملة SAR
            context = browser.new_context(
                locale='ar-SA',
                geolocation={'latitude': 24.7136, 'longitude': 46.6753}, 
                permissions=['geolocation']
            )
            page = context.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_load_state('networkidle')

            if action == "price":
                # ملاحظة: كلاسات شي إن تتغير، يجب تحديث الـ selectors لاحقاً بناءً على فحص الصفحة
                # هذا كود افتراضي لمحاكاة سحب السعر الأسود والأحمر
                try:
                    # محاولة سحب السعر الأساسي والمخفض (يجب تعديل الـ CSS Selectors لاحقاً)
                    black_price_text = page.locator('.original-price').inner_text() # افتراضي
                    red_price_text = page.locator('.discount-price').inner_text() # افتراضي
                    
                    black_price = float(black_price_text.replace('SAR', '').strip())
                    red_price = float(red_price_text.replace('SAR', '').strip())
                    
                    final_text = calculate_price_logic(black_price, red_price)
                except:
                    # في حال لم يجد سعر أحمر
                    final_text = "السعر الأساسي: لم يتم تحديد الهيكل بعد (تحتاج ضبط Selectors)"

                bot.edit_message_text(f"✅ النتائج:\n\n{final_text}", chat_id=call.message.chat.id, message_id=msg.message_id)

            elif action == "screen":
                screenshot_path = "product.png"
                page.screenshot(path=screenshot_path)
                with open(screenshot_path, 'rb') as photo:
                    bot.send_photo(call.message.chat.id, photo, caption="📸 لقطة شاشة للمنتج")
                bot.delete_message(call.message.chat.id, msg.message_id)

            elif action == "images":
                # سحب الصور وإضافة شعار سوقمي
                bot.edit_message_text("جاري سحب الصور وإضافة الهوية البصرية...", chat_id=call.message.chat.id, message_id=msg.message_id)
                # هنا يتم برمجة جلب الـ src للصور، دمج اللوجو باستخدام مكتبة Pillow (PIL)
                # وإرسالها كألبوم (MediaGroup)
                
            elif action == "cart":
                bot.edit_message_text("🛒 قريباً: ميزة سحب السلة تتطلب رابط 'مشاركة السلة' من العميل للمرور على عناصرها.", chat_id=call.message.chat.id, message_id=msg.message_id)

            browser.close()
            
    except Exception as e:
        bot.edit_message_text(f"❌ حدث خطأ: {str(e)}", chat_id=call.message.chat.id, message_id=msg.message_id)

print("Bot is running...")
bot.infinity_polling()
