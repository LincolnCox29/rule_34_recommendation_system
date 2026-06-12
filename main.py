import asyncio
from dotenv import load_dotenv
import os
from user import User
import torch

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

R34_API_KEY = os.getenv("R34_API_KEY")
R34_USER_ID = os.getenv("R34_USER_ID")

def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="To feed",
                    callback_data="feed"
                ),
                InlineKeyboardButton(
                    text="Settings",
                    callback_data="settings"
                )
            ]
        ]
    )

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):

    await callback.message.answer(
        "Choose action:",
        reply_markup=main_menu()
    )

    await callback.answer()

def feed_keyboard(post_id, liked=False, disliked=False):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❤️ Liked" if liked else "🤍 Like",
                    callback_data=f"like:{1 if liked else 0}:{post_id}"
                ),
                InlineKeyboardButton(
                    text="Next",
                    callback_data=f"feed:{post_id}"
                )   
            ],
            [
                InlineKeyboardButton(
                    text="🙈 Less like this" if disliked else "🐵 Less like this",
                    callback_data=f"dislike:{1 if disliked else 0}:{post_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Back",
                    callback_data="main_menu"
                ), 
            ]
        ]
    )

@dp.callback_query(F.data == "turn_AI_filter")
async def turn_AI_filter(callback: CallbackQuery):

    user = User(callback.from_user.id)
    user.config["ai_filter"] = not user.config["ai_filter"]

    await callback.message.edit_text(
        "Settings",
        reply_markup=settings_menu(user)
    )

    user.save_user_data()

    await callback.answer()

def settings_menu(user):

    ai_filter = user.config["ai_filter"]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ AI filter enabled" if ai_filter else "❌ AI filter disabled",
                    callback_data="turn_AI_filter"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Back",
                    callback_data="main_menu"
                )
            ]
        ]
    )

@dp.callback_query(F.data == "settings")
async def settings(callback: CallbackQuery):

    user = User(callback.from_user.id)

    await callback.message.edit_text(
        "Settings",
        reply_markup=settings_menu(user)
    )

    await callback.answer()

# ===== Start =====

@dp.message(F.text == "/start")
async def start(message: Message):

    await message.answer(
        "Choose action:",
        reply_markup=main_menu()
    )

# ===== Open Feed =====

@dp.callback_query(F.data.startswith("feed"))
async def open_feed(callback: CallbackQuery):

    user = User(callback.from_user.id)

    data = callback.data
    if ":" in data:
        post_id = data.split(":")[1]

        post = user.posts_cache.get(post_id)

        if post:
            user.skip_post(post)

    post = await user.next_post()
    if post == None:
        return

    user.update_posts_cache(post)

    image_url = (
        post.get("sample_url")
        or post.get("file_url")
        or post.get("preview_url")
    )
    print(post)

    formatted_tags = " ".join(
        f"#{tag}"
        for tag in post["tags"].split()[:20]
    )

    await callback.message.answer_photo(
        photo=image_url,
        caption= f"Score: {post['score']}\nTags: {formatted_tags}",
        reply_markup=feed_keyboard(str(post["id"]))
    )

    await callback.answer()

# ===== Like =====

@dp.callback_query(F.data.startswith("like:"))
async def like_post(callback: CallbackQuery):

    user = User(callback.from_user.id)

    isLiked = int(callback.data.split(":")[1])
    if isLiked:
        return

    post_id = callback.data.split(":")[2]

    print(post_id)

    await callback.message.edit_reply_markup(
        reply_markup=feed_keyboard(post_id, liked=True)
    )

    post = user.posts_cache.get(post_id)
    user.like_post(post)

    await callback.answer("Added to favorites")

@dp.callback_query(F.data.startswith("dislike:"))
async def dislike_post_ui(callback: CallbackQuery):

    user = User(callback.from_user.id)

    isDisliked = int(callback.data.split(":")[1])
    if isDisliked:
        return

    post_id = callback.data.split(":")[2]

    print("disliked: ", post_id)

    await callback.message.edit_reply_markup(
        reply_markup=feed_keyboard(post_id, disliked=True)
    )

    post = user.posts_cache.get(post_id)
    user.dislike_post(post)

    await callback.answer("Less like this")

# ===== Main =====

def machine_configuration():
    print("Torch:", torch.__version__)
    print("CUDA:", torch.version.cuda)
    print("Available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))

async def main():
    machine_configuration()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())