import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

API_ID = '22710783'
API_HASH = '616ea341acfed51f916506c20b8a0a44'
BOT_TOKEN = '6992564545:AAEz2LhBcJpzcri4ElLB4w7Vs63NB8JG5Oo'
MONGO_URI = "mongodb+srv://test:test@cluster0.q9llhnj.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  
mongo_client = MongoClient(MONGO_URI)
db = mongo_client['telegram_bot']
channels_collection = db['channels']
app = Client("custom_caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Use /add <channel_id> to add a channel.")
@app.on_message(filters.command("add"))
async def add_channel(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /add <channel_id>")
        return

    channel_id = message.command[1]
    await message.reply_text(f"Please send the custom caption for channel {channel_id}:")

    @app.on_message(filters.text & filters.private, group=1)
    async def get_caption(client, msg):
        caption = msg.text
        await message.reply_text("Please send the custom button text and URL in the format: ButtonText,URL")
        
        @app.on_message(filters.text & filters.private, group=2)
        async def get_button(client, msg):
            try:
                button_text, button_url = msg.text.split(',')
                channels_collection.update_one(
                    {'channel_id': channel_id},
                    {'$set': {'caption': caption, 'button_text': button_text, 'button_url': button_url}},
                    upsert=True
                )
                await msg.reply_text("Channel and custom caption added successfully!")
            except ValueError:
                await msg.reply_text("Invalid format. Please send the custom button text and URL in the format: ButtonText,URL")
@app.on_message(filters.channel)
async def handle_channel_message(client, message):
    channel_id = str(message.chat.id)
    channel_data = channels_collection.find_one({'channel_id': channel_id})

    if channel_data:
        caption = channel_data.get('caption', '')
        button_text = channel_data.get('button_text', '')
        button_url = channel_data.get('button_url', '')

        if caption and button_text and button_url:
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton(button_text, url=button_url)]]
            )

            if message.media:
                await message.edit_caption(caption=caption, reply_markup=reply_markup)
            else:
                await message.edit_text(text=caption, reply_markup=reply_markup)


         #   await message.edit(caption=caption, reply_markup=reply_markup
    if __name__ == "__main__":
    app.run()
