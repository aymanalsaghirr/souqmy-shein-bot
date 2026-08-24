import os
import telebot
import cloudscraper
from bs4 import BeautifulSoup

# توكن البوت الخاص بك
TOKEN = "8871899951:AAHl7umC0vzRbwsu4bWs3Dmejlv5tP7jl9g"
bot = telebot.TeleBot(TOKEN)

# دالة سحب بيانات شي إن مع تخطي الحماية (Cloudflare)
def scrape_shein_product(url):
    try:
        # إنشاء سكرابر يتخفي كمتصفح حقيقي لتجاوز الحماية
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'firefox',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        response = scraper.get(url, timeout=15)
        if response.status_code != 200:
            return {"error": "تعذر الوصول للمنتج، رمز الاستجابة: " + str(response.status_code)}

        soup = BeautifulSoup(response.text, 'html.parser')

        # استخراج اسم المنتج
        title_meta = soup.find('meta', property='og:title')
        title = title_meta['content'].replace('- SHEIN', '').strip() if title_meta else "منتج شي إن"

        # استخراج السعر بالريال السعودي (من النسخة السعودية)
        price_meta = soup.find('meta', property='og:price:amount')
        price = price_meta['content'] if price_meta else "غير متوفر"

        return {
            "title": title,
            "price": price
        }
    except Exception as e:
        return {"error": str(e)}

# استقبال رسائل الروابط من الموظفين
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    
    if "shein.com" in url or "shein.top" in url:
        sent_msg = bot.reply_to(message, "⏳ جاري جلب البيانات وتخطي الحماية من شي إن السعودية...")
        
        data = scrape_shein_product(url)
        
        if "error" in data:
            bot.edit_message_text(f"❌ حدث خطأ: {data['error']}", chat_id=message.chat.id, message_id=sent_msg.message_id)
        else:
            reply_text = f"✅ **تم سحب البيانات بنجاح!**\n\n"
            reply_text += f"🏷 **المنتج:** {data['title']}\n"
            reply_text += f"💰 **السعر:** {data['price']} ريال سعودي\n"
            
            bot.edit_message_text(reply_text, chat_id=message.chat.id, message_id=sent_msg.message_id, parse_mode="Markdown")
    else:
        bot.reply_to(message, "مرحباً بك في نظام تسعير سوقمي! 🚀\nأرسل لي رابط منتج من شي إن للبدء.")

print("Bot is running...")
bot.infinity_polling()
