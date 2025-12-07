import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from groq import Groq
from google import genai
from google.genai import types
import base64
from PIL import Image
import io

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

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot created by Rudra! Send me a message.")

# Store chat history: chat_id -> list of messages
chat_histories = {}

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = update.effective_chat.id
    
    # Check for image generation request
    if user_message.lower().startswith(("create an image", "generate an image","generate image", "create image")):
        try:
            await context.bot.send_message(chat_id=chat_id, text="Generating image... (this might take a moment)")
            
            if not gemini_client:
                await context.bot.send_message(chat_id=chat_id, text="Sorry, Gemini API key is missing.")
                return

            response = gemini_client.models.generate_images(
                model='imagen-4.0-generate-001',
                prompt=user_message,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                )
            )
            
            # response.generated_images[0].image is a PIL Image
            img_byte_arr = io.BytesIO()
            response.generated_images[0].image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            await context.bot.send_photo(chat_id=chat_id, photo=img_byte_arr)
            return
        except Exception as e:
            logging.error(f"Error generating image: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f"Sorry, I couldn't generate the image. Error: {e}")
            return

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
            "content": "You are an AI designed by Rudra to help pentesters, AI/ML enthusiasts and security researchers. Answer the user in brief."
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

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    photo_file = await update.message.photo[-1].get_file()
    
    # Download file to memory
    image_stream = io.BytesIO()
    await photo_file.download_to_memory(out=image_stream)
    image_stream.seek(0)
    
    user_caption = update.message.caption or ""
    
    # Check for edit request
    if "edit" in user_caption.lower() or "change" in user_caption.lower():
        try:
            await context.bot.send_message(chat_id=chat_id, text="Editing image with Gemini... (this might take a moment)")
            
            if not gemini_client:
                await context.bot.send_message(chat_id=chat_id, text="Sorry, Gemini API key is missing.")
                return

            # Reset stream for PIL
            image_stream.seek(0)
            pil_image = Image.open(image_stream)
            
            # Workaround: Describe + Generate
            desc_response = gemini_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=[
                    "Describe this image in detail so I can recreate it, but apply this change: " + user_caption,
                    pil_image
                ]
            )
            new_prompt = desc_response.text
            
            # Generate new image
            gen_response = gemini_client.models.generate_images(
                model='imagen-4.0-generate-001',
                prompt=new_prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                )
            )
            
            img_byte_arr = io.BytesIO()
            gen_response.generated_images[0].image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            await context.bot.send_photo(chat_id=chat_id, photo=img_byte_arr, caption="Here is the edited version (re-generated).")
            return
        except Exception as e:
            logging.error(f"Error editing image: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f"Sorry, I couldn't edit the image. Error: {e}")
            return

    # Default: Analysis (Groq)
    # Reset stream for reading again
    image_stream.seek(0)
    base64_image = base64.b64encode(image_stream.read()).decode('utf-8')
    
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
