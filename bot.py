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
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_caption},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
        )
        response_content = chat_completion.choices[0].message.content
        await context.bot.send_message(chat_id=chat_id, text=response_content)
    except Exception as e:
        logging.error(f"Error analyzing image: {e}")
        await context.bot.send_message(chat_id=chat_id, text="Sorry, I couldn't analyze that image.")

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
    photo_handler = MessageHandler(filters.PHOTO, handle_photo)
    
    application.add_handler(start_handler)
    application.add_handler(chat_handler)
    application.add_handler(photo_handler)
    
    print("Bot is running...")
    application.run_polling()
