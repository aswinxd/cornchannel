import pyrogram 
import re
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = '22710783'
API_HASH = '616ea341acfed51f916506c20b8a0a44'
BOT_TOKEN = '6762340943:AAHrbrMnDIZNAAN709sRDJK27AaMLc43Fcs'
MONGO_URI = "mongodb+srv://test:test@cluster0.q9llhnj.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  
mongo_client = MongoClient(MONGO_URI)
db = mongo_client['bot2']
channels_collection = db['channels2']
app = Client("custom_caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_states = {}

@app.on_message(filters.command("channels"))
async def list_channels(client, message):
    user_id = message.from_user.id
    channels = channels_collection.find({'user_id': user_id})
    buttons = []

    for channel in channels:
        channel_name = channel.get('channel_name', 'Unknown')
        buttons.append([InlineKeyboardButton(f"{channel_name} ({channel['channel_id']})", callback_data=f"channel_{channel['channel_id']}")])

    if buttons:
        await message.reply_text("Your channels:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply_text("You have no channels added. Use /add <channel_id> to add a channel.")
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Use /add <channel_id> to add a channel.")
    
@app.on_message(filters.command("add"))
async def add_channel(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /add <channel_id>")
        return

    channel_id = message.command[1]
    user_id = message.from_user.id
    
    # Fetch channel information
    try:
        chat = await client.get_chat(channel_id)
        channel_name = chat.title
    except Exception as e:
        await message.reply_text(f"Failed to add channel: {str(e)}")
        return

    channels_collection.update_one(
        {'channel_id': channel_id, 'user_id': user_id},
        {'$set': {'channel_name': channel_name, 'caption': '', 'button_text': '', 'button_url': ''}},
        upsert=True
    )

    await message.reply_text(f"Channel {channel_name} ({channel_id}) added. Use `/set_caption {channel_id}` to set a caption and `/set_button {channel_id}` to set a button.")
@app.on_message(filters.command("set_caption"))
async def set_caption(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /set_caption <channel_id>")
        return

    channel_id = message.command[1]
    user_id = message.from_user.id
    user_states[user_id] = {'action': 'set_caption', 'channel_id': channel_id}
    await message.reply_text("Please send the custom caption:")

@app.on_message(filters.command("set_button"))
async def set_button(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /set_button <channel_id>")
        return

    channel_id = message.command[1]
    user_id = message.from_user.id
    user_states[user_id] = {'action': 'set_button', 'channel_id': channel_id}
    await message.reply_text("Please send the custom button text and URL in the format: ButtonText,URL")

@app.on_message(filters.text & filters.private)
async def handle_private_message(client, message):
    user_id = message.from_user.id
    if user_id in user_states:
        state = user_states[user_id]
        action = state.get('action')
        channel_id = state.get('channel_id')

        if action == 'set_caption':
            caption = message.text
            channels_collection.update_one(
                {'channel_id': channel_id, 'user_id': user_id},
                {'$set': {'caption': caption}},
            )
            await message.reply_text("Caption updated successfully!")
            del user_states[user_id]

        elif action == 'set_button':
            try:
                button_text, button_url = message.text.split(',')
                channels_collection.update_one(
                    {'channel_id': channel_id, 'user_id': user_id},
                    {'$set': {'button_text': button_text, 'button_url': button_url}},
                )
                await message.reply_text("Button updated successfully!")
            except ValueError:
                await message.reply_text("Invalid format. Please send the custom button text and URL in the format: ButtonText,URL")
            del user_states[user_id]


@app.on_callback_query(filters.regex(r"channel_(.*)"))
async def channel_details(client, callback_query):
    channel_id = callback_query.data.split('_')[1]
    user_id = callback_query.from_user.id
    channel = channels_collection.find_one({'channel_id': channel_id, 'user_id': user_id})

    if channel:
        await callback_query.message.reply_text(
            f"Channel ID: {channel_id}\nCaption: {channel['caption']}\nButton: {channel['button_text']}, {channel['button_url']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Edit Caption", callback_data=f"edit_caption_{channel_id}")],
                [InlineKeyboardButton("Edit Button", callback_data=f"edit_button_{channel_id}")],
                [InlineKeyboardButton("Remove Channel", callback_data=f"remove_channel_{channel_id}")]
            ])
        )

@app.on_callback_query(filters.regex(r"edit_caption_(.*)"))
async def edit_caption(client, callback_query):
    channel_id = callback_query.data.split('_')[2]
    user_id = callback_query.from_user.id
    user_states[user_id] = {'action': 'edit_caption', 'channel_id': channel_id}
    await callback_query.message.reply_text(f"Please send the new caption for channel {channel_id}:")

@app.on_callback_query(filters.regex(r"edit_button_(.*)"))
async def edit_button(client, callback_query):
    channel_id = callback_query.data.split('_')[2]
    user_id = callback_query.from_user.id
    user_states[user_id] = {'action': 'edit_button', 'channel_id': channel_id}
    await callback_query.message.reply_text(f"Please send the new button text and URL for channel {channel_id} in the format: ButtonText,URL")

@app.on_callback_query(filters.regex(r"remove_channel_(.*)"))
async def remove_channel(client, callback_query):
    channel_id = callback_query.data.split('_')[2]
    user_id = callback_query.from_user.id
    channels_collection.delete_one({'channel_id': channel_id, 'user_id': user_id})
    await callback_query.message.reply_text("Channel removed successfully!")

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
            
            # else:
            #     await message.edit_text(text=caption, reply_markup=reply_markup)

if __name__ == "__main__":
    app.run()
