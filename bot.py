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

# Store chat history: chat_id -> list of messages
chat_histories = {}

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = update.effective_chat.id
    
    # Initialize history for this chat if not present
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    
    # Add user message to history
    chat_histories[chat_id].append({"role": "user", "content": user_message})
    
    # Keep only last 10 messages (5 exchanges)
    if len(chat_histories[chat_id]) > 10:
        chat_histories[chat_id] = chat_histories[chat_id][-10:]
        
    # Prepare messages for API call (system prompt + history)
    messages = [
        {
            "role": "system",
            "content": "You are an AI designed by Rudra to help pentesters and security researchers. Answer the user in brief."
        }
    ] + chat_histories[chat_id]

    models = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "meta-llama/llama-4-scout-17b-16e-instruct"
    ]

    response_content = None
    
    for model in models:
        try:
            logging.info(f"Trying model: {model}")
            chat_completion = client.chat.completions.create(
                messages=messages,
                model=model,
            )
            response_content = chat_completion.choices[0].message.content
            break # Success, exit loop
        except Exception as e:
            logging.error(f"Error with model {model}: {e}")
            continue # Try next model

    if response_content:
        # Add assistant response to history
        chat_histories[chat_id].append({"role": "assistant", "content": response_content})
        
        # Split message if it's too long for Telegram (limit is 4096 chars)
        max_length = 4096
        for i in range(0, len(response_content), max_length):
            chunk = response_content[i:i+max_length]
            await context.bot.send_message(chat_id=chat_id, text=chunk)
    else:
        await context.bot.send_message(chat_id=chat_id, text="Sorry, I tried all available models but couldn't generate a response.")

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
