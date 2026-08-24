import os
import re
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

# قاموس لتخزين روابط المستخدمين مؤقتاً
user_data = {}

def calculate_price_logic(black_price, red_price=None):
    if not red_price or red_price >= black_price:
        return f"السعر الأساسي: {black_price} SAR"
    
    discount = ((black_price - red_price) / black_price) * 100
    
    if discount <= 5.0:
        return f"السعر الأصلي: {black_price} SAR\nالسعر بعد الخصم ({discount:.1f}%): {red_price} SAR"
    else:
        return f"السعر المعتمد: {black_price} SAR (نسبة الخصم تتجاوز 5%، لا يتم تطبيق الخصم الإضافي)"

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    
    if "shein" in url:
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
            
            # إعداد المتصفح كـ "هاتف ذكي"
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
            
            # الانتظار حتى يظهر هيكل المنتج تماماً وتجاوز الشاشة البيضاء
            try:
                page.wait_for_selector('.product-intro, .goods-detail', timeout=15000)
            except:
                pass
            page.wait_for_timeout(3000) # وقت إضافي لاستقرار الصور والأسعار

            if action == "price":
                try:
                    # استخراج الأسعار بطريقة ذكية تبحث عن الحاويات في صفحة شي إن
                    price_data = page.evaluate("""() => {
                        const originalElem = document.querySelector('.original-price, .goods-price__sale, [class*="original"], [class*="price"]');
                        const discountElem = document.querySelector('.discount-price, .goods-price__current, [class*="discount"], [class*="current-price"]');
                        return {
                            original: originalElem ? originalElem.innerText : null,
                            discount: discountElem ? discountElem.innerText : null
                        };
                    }""")
                    
                    def extract_num(text):
                        if not text: return None
                        match = re.search(r'[\d,.]+', text.replace(',', ''))
                        return float(match.group()) if match else None

                    black_price = extract_num(price_data.get('original'))
                    red_price = extract_num(price_data.get('discount'))
                    
                    # إذا وجد سعراً واحداً فقط، نعتبره الأساسي
                    if not black_price and red_price:
                        black_price = red_price
                        red_price = None

                    if black_price:
                        final_text = calculate_price_logic(black_price, red_price)
                    else:
                        final_text = "⚠️ لم يتم جلب الأسعار تلقائياً، يرجى التأكد من الرابط."
                except Exception as e:
                    final_text = f"❌ خطأ في قراءة الأسعار: {str(e)}"

                bot.edit_message_text(f"✅ النتائج:\n\n{final_text}", chat_id=chat_id, message_id=msg.message_id)

            elif action == "screen":
                screenshot_path = "product.png"
                # التقاط الشاشة الظاهرة فقط للجوال (بدون مساحات بيضاء وبدون إطالة الصفحة)
                page.screenshot(path=screenshot_path, full_page=False)

                with open(screenshot_path, 'rb') as photo:
                    bot.send_photo(chat_id, photo, caption="📸 صورة المنتج (تصميم جوال واضح) من سوقمي 🇸🇦")
                bot.delete_message(chat_id, msg.message_id)
            
            elif action == "images":
                 bot.edit_message_text("جاري سحب الصور وإضافة الهوية البصرية...", chat_id=chat_id, message_id=msg.message_id)
            
            elif action == "cart":
                 bot.edit_message_text("🛒 قريباً: ميزة سحب السلة...", chat_id=chat_id, message_id=msg.message_id)

            browser.close()
            
    except Exception as e:
        bot.edit_message_text(f"❌ حدث خطأ عام: {str(e)}", chat_id=chat_id, message_id=msg.message_id)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    print("Bot is running...")
    bot.remove_webhook()
    bot.infinity_polling()
