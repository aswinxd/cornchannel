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
BOT_TOKEN = '6992564545:AAEz2LhBcJpzcri4ElLB4w7Vs63NB8JG5Oo'
MONGO_URI = "mongodb+srv://test:test@cluster0.q9llhnj.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  
mongo_client = MongoClient(MONGO_URI)
db = mongo_client['telegram_bot']
channels_collection = db['channels']
app = Client("custom_caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_states = {}

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

    try:
        chat = await client.get_chat(channel_id)
        channel_name = chat.title
    except Exception as e:
        await message.reply_text(f"Failed to fetch channel details: {str(e)}")
        return

    channels_collection.update_one(
        {'channel_id': channel_id, 'user_id': user_id},
        {'$set': {'channel_name': channel_name, 'caption': '', 'button_text': '', 'button_url': ''}},
        upsert=True
    )

    await message.reply_text(f"Channel '{channel_name}' added. Use /channels to manage your channels.")
    

@app.on_message(filters.command("add_caption"))
async def add_caption(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /add_caption <channel_id>")
        return

    channel_id = message.command[1]
    user_id = message.from_user.id

    user_states[user_id] = {'action': 'add_caption', 'channel_id': channel_id}
    await message.reply_text(f"Please send the custom caption for channel {channel_id}:")

@app.on_message(filters.text & filters.private)
async def handle_caption_input(client, message):
    user_id = message.from_user.id

    if user_id in user_states and user_states[user_id]['action'] == 'add_caption':
        channel_id = user_states[user_id]['channel_id']
        caption = message.text

        channels_collection.update_one(
            {'channel_id': channel_id, 'user_id': user_id},
            {'$set': {'caption': caption}},
        )
        await message.reply_text("Caption updated successfully!")
        del user_states[user_id]  
        
@app.on_message(filters.text & filters.private)
async def handle_button_input(client, message):
    user_id = message.from_user.id

    if user_id in user_states and user_states[user_id]['action'] == 'add_button':
        channel_id = user_states[user_id]['channel_id']
        try:
            button_text, button_url = message.text.split(',')
            button_url = button_url.strip()

            channels_collection.update_one(
                {'channel_id': channel_id, 'user_id': user_id},
                {'$set': {'button_text': button_text.strip(), 'button_url': button_url}},
            )
            await message.reply_text("Button updated successfully!")
            del user_states[user_id]  
        except ValueError:
            await message.reply_text("Invalid format. Please send the custom button text and URL in the format: ButtonText,URL")
    


@app.on_message(filters.command("channels") & filters.private)
async def list_channels(client, message):
    user_id = message.from_user.id

    user_channels = channels_collection.find({'user_id': user_id})

    if user_channels.count() == 0:
        await message.reply_text("You have not added any channels.")
        return

    
    buttons = []
    for channel in user_channels:
        channel_name = (await client.get_chat(channel['channel_id'])).title  # Fetch the channel name
        buttons.append(
            [InlineKeyboardButton(f"{channel_name} ({channel['channel_id']})", callback_data=f"manage_{channel['channel_id']}")]
        )


    reply_markup = InlineKeyboardMarkup(buttons)

    await message.reply_text("Your channels:", reply_markup=reply_markup)

@app.on_callback_query(filters.regex(r"^manage_(\d+)$"))
async def manage_channel(client, callback_query):
    channel_id = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id

    # Fetch the channel details from the database
    channel_data = channels_collection.find_one({'channel_id': channel_id, 'user_id': user_id})

    if not channel_data:
        await callback_query.answer("Channel not found or you do not have permission to manage this channel.", show_alert=True)
        return

    # Create buttons for editing caption, button, and removing the channel
    buttons = [
        [InlineKeyboardButton("Edit Caption", callback_data=f"edit_caption_{channel_id}")],
        [InlineKeyboardButton("Edit Button", callback_data=f"edit_button_{channel_id}")],
        [InlineKeyboardButton("Remove Channel", callback_data=f"remove_channel_{channel_id}")],
        [InlineKeyboardButton("Back", callback_data="channels")]
    ]

    reply_markup = InlineKeyboardMarkup(buttons)

    await callback_query.message.edit_text(f"Manage channel {channel_data['channel_id']}:", reply_markup=reply_markup)

@app.on_callback_query(filters.regex(r"^edit_caption_(\d+)$"))
async def edit_caption_prompt(client, callback_query):
    channel_id = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id

    user_states[user_id] = {'action': 'add_caption', 'channel_id': channel_id}
    await callback_query.message.edit_text("Please send the new caption:")

@app.on_callback_query(filters.regex(r"^edit_button_(\d+)$"))
async def edit_button_prompt(client, callback_query):
    channel_id = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id

    user_states[user_id] = {'action': 'add_button', 'channel_id': channel_id}
    await callback_query.message.edit_text("Please send the new button text and URL in the format: ButtonText,URL")

@app.on_callback_query(filters.regex(r"^remove_channel_(\d+)$"))
async def remove_channel(client, callback_query):
    channel_id = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id

    channels_collection.delete_one({'channel_id': channel_id, 'user_id': user_id})
    await callback_query.message.edit_text("Channel removed successfully.")


    await list_channels(client, callback_query.message)
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
    await callback_query.message.reply_text(f"Please send the new caption for channel {channel_id}:")

    @app.on_message(filters.text & filters.private, group=3)
    async def get_new_caption(client, msg):
        caption = msg.text
        channels_collection.update_one(
            {'channel_id': channel_id, 'user_id': user_id},
            {'$set': {'caption': caption}},
        )
        await msg.reply_text("Caption updated successfully!")

@app.on_callback_query(filters.regex(r"edit_button_(.*)"))
async def edit_button(client, callback_query):
    channel_id = callback_query.data.split('_')[2]
    user_id = callback_query.from_user.id
    await callback_query.message.reply_text(f"Please send the new button text and URL for channel {channel_id} in the format: ButtonText,URL")

    @app.on_message(filters.text & filters.private, group=4)
    async def get_new_button(client, msg):
        try:
            button_text, button_url = msg.text.split(',')
            channels_collection.update_one(
                {'channel_id': channel_id, 'user_id': user_id},
                {'$set': {'button_text': button_text, 'button_url': button_url}},
            )
            await msg.reply_text("Button updated successfully!")
        except ValueError:
            await msg.reply_text("Invalid format. Please send the custom button text and URL in the format: ButtonText,URL")

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

    if channel_data and 'caption' in channel_data:
        caption = channel_data['caption']
        button_text = channel_data.get('button_text')
        button_url = channel_data.get('button_url')

        if button_text and button_url:
            try:
                reply_markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(button_text, url=button_url)]]
                )
                await message.edit_text(text=caption, reply_markup=reply_markup)
            except pyrogram.errors.exceptions.bad_request_400.ButtonUrlInvalid:
                await message.reply_text("The button URL is invalid. Please check the URL format.")
        else:
            await message.edit_text(text=caption)
            
if __name__ == "__main__":
    app.run()
