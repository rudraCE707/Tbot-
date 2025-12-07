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

import google.generativeai as genai
# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot created by Rudra! Send me a message.")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    
    # Check for image generation request
    if user_message.lower().startswith(("create image", "generate image")):
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Generating image... (this might take a moment)")
            
            # Use 'imagen-3.0-generate-001' if available, or fallback/notify
            model = genai.GenerativeModel('imagen-3.0-generate-001')
            response = model.generate_images(
                prompt=user_message,
                number_of_images=1,
            )
            
            from io import BytesIO
            img_byte_arr = BytesIO()
            response.images[0].save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img_byte_arr)
            return
        except Exception as e:
            logging.error(f"Error generating image: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Sorry, I couldn't generate the image. Error: {e}")
            return

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "You are an AI designed by Rudra to help pentesters, AI/ML enthusiasts and security researchers. Answer the following question of the user in brief: " + user_message,
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

import base64

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    photo_file = await update.message.photo[-1].get_file()
    
    # Download file to memory
    from io import BytesIO
    image_stream = BytesIO()
    await photo_file.download_to_memory(out=image_stream)
    image_stream.seek(0)
    
    # Encode to base64
    base64_image = base64.b64encode(image_stream.read()).decode('utf-8')
    
    user_caption = update.message.caption or ""
    
    # Check for edit request
    if "edit" in user_caption.lower() or "change" in user_caption.lower():
        try:
            await context.bot.send_message(chat_id=chat_id, text="Editing image with Gemini... (this might take a moment)")
            
            # Reset stream for PIL
            image_stream.seek(0)
            from PIL import Image
            pil_image = Image.open(image_stream)
            
            # Workaround: Describe + Generate
            model_desc = genai.GenerativeModel('gemini-1.5-flash')
            desc_response = model_desc.generate_content([
                "Describe this image in detail so I can recreate it, but apply this change: " + user_caption,
                pil_image
            ])
            new_prompt = desc_response.text
            
            # Generate new image
            model_gen = genai.GenerativeModel('imagen-3.0-generate-001')
            gen_response = model_gen.generate_images(
                prompt=new_prompt,
                number_of_images=1,
            )
            
            from io import BytesIO
            img_byte_arr = BytesIO()
            gen_response.images[0].save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            await context.bot.send_photo(chat_id=chat_id, photo=img_byte_arr, caption="Here is the edited version (re-generated).")
            return
        except Exception as e:
            logging.error(f"Error editing image: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f"Sorry, I couldn't edit the image. Error: {e}")
            return

    user_caption = user_caption or "What is in this image?"

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
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
