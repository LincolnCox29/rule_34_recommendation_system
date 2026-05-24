import asyncio
import random
import requests
from dotenv import load_dotenv
import os

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

like_tags = {}
posts_cache = {}
fav = []

AI_filter = False

IGNORE_TAGS = {
    "1girl",
    "2girls",
    "solo",
    "smile",
    "looking_at_viewer",
    "rating_explicit"
}

def get_random_post():

    for i in range(5):

        if i == 4:
            query = []
        else:
            query = build_query()

        if len(query.split()) >= 3:
            pid = random.randint(0, 20)
        else:
            pid = random.randint(0, 200)

        params = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "json": 1,
            "limit": 20,
            "pid": pid,
            "tags": query,
            "api_key": os.getenv("R34_API_KEY"),
            "user_id": os.getenv("R34_USER_ID")
        }

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        try:

            response = requests.get(
                "https://api.rule34.xxx/index.php",
                params=params,
                headers=headers,
                timeout=10
            )

            posts = response.json()

            if not posts:
                continue

            return random.choice(posts)

        except Exception as e:
            print(e)
            continue

    return None

def build_query():

    query = []

    positive_tags = {
        tag: score
        for tag, score in like_tags.items()
        if score > 0
    }

    negative_tags = {
        tag: score
        for tag, score in like_tags.items()
        if score < 0
    }

    if positive_tags:

        tags = list(positive_tags.keys())

        weights = [
            score ** 0.5
            for score in positive_tags.values()
        ]

        k = random.choices(
            [1, 2],
            weights=[85, 15]
        )[0]

        selected_tags = random.choices(
            tags,
            weights=weights,
            k=k
        )

        query.extend(set(selected_tags))

    if negative_tags:

        disliked = sorted(
            negative_tags.items(),
            key=lambda x: x[1]
        )

        query.extend(
            f"-{tag}"
            for tag, _ in disliked[:2]
        )

    if random.random() < 0.15:
        query = []

    if AI_filter:

        query.extend([
            "-ai_generated",
            "-stable_diffusion",
            "-midjourney",
            "-novelai"
        ])

    return " ".join(query)

# ===== Main Menu =====

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

# ===== Feed Keyboard =====

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
                    callback_data="feed"
                )   
            ],
            [
                InlineKeyboardButton(
                    text="🙈 Less like this",
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

# ===== Settings =====

@dp.callback_query(F.data == "turn_AI_filter")
async def turn_AI_filter(callback: CallbackQuery):

    global AI_filter

    AI_filter = not AI_filter

    await callback.message.edit_text(
        "Settings",
        reply_markup=settings_menu()
    )

    await callback.answer()

def settings_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ AI filter enabled" if AI_filter else "❌ AI filter disabled",
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

    await callback.message.edit_text(
        "Settings",
        reply_markup=settings_menu()
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

decay_counter = 0

@dp.callback_query(F.data == "feed")
async def open_feed(callback: CallbackQuery):

    global decay_counter
    decay_counter += 1
    if decay_counter == 20:
        for tag in like_tags:
            if like_tags[tag] > 0:
                like_tags[tag] *= 0.97
            elif like_tags[tag] < 0:
                like_tags[tag] *= 0.9
        decay_counter = 0

    post = get_random_post()
    if post == None:
        return
    
    posts_cache[post["id"]] = post
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
        reply_markup=feed_keyboard(post["id"])
    )

    await callback.answer()

# ===== Like =====

@dp.callback_query(F.data.startswith("like:"))
async def like_post(callback: CallbackQuery):

    isLiked = int(callback.data.split(":")[1])
    if isLiked:
        return

    post_id = callback.data.split(":")[2]

    print(post_id)

    await callback.message.edit_reply_markup(
        reply_markup=feed_keyboard(post_id, liked=True)
    )

    post = posts_cache.get(int(post_id))
    tags = post["tags"].split(" ")

    for tag in tags:
        if tag in IGNORE_TAGS:
            continue

        if tag not in like_tags:
            like_tags[tag] = 0

        like_tags[tag] += 1

    await callback.answer("Added to favorites")

@dp.callback_query(F.data.startswith("dislike:"))
async def dislike_post(callback: CallbackQuery):

    isDisliked = int(callback.data.split(":")[1])
    if isDisliked:
        return

    post_id = callback.data.split(":")[2]

    print(post_id)

    await callback.message.edit_reply_markup(
        reply_markup=feed_keyboard(post_id, disliked=True)
    )

    post = posts_cache.get(int(post_id))
    tags = post["tags"].split(" ")

    for tag in tags:
        if tag in IGNORE_TAGS:
            continue

        if tag not in like_tags:
            like_tags[tag] = 0

        like_tags[tag] -= 1 

    await callback.answer("Less like this")

# ===== Main =====

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())