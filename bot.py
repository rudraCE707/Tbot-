import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from groq import Groq

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot created by Rudra! Send me a message.")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "You are an AI designed by Rudra to help pentesters and security researchers. Answer the following question of the user in brief: " + user_message,
                }
            ],
            model="openai/gpt-oss-120b",
        )
        response_content = chat_completion.choices[0].message.content
        
        # Split message if it's too long for Telegram (limit is 4096 chars)
        max_length = 4096
        for i in range(0, len(response_content), max_length):
            chunk = response_content[i:i+max_length]
            await context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)
    except Exception as e:
        logging.error(f"Error getting response from Groq: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I encountered an error processing your request.")

if __name__ == '__main__':
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env file.")
        exit(1)
    if not GROQ_API_KEY:
        print("Error: GROQ_API_KEY not found in .env file.")
        exit(1)

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    chat_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), chat)
    
    application.add_handler(start_handler)
    application.add_handler(chat_handler)
    
    print("Bot is running...")
    application.run_polling()
