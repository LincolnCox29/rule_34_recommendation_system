import asyncio
import random
import requests
from dotenv import load_dotenv
import os
import math
import json
from user import User

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

TAGS_POP = None
def load_tags_pop():
    global TAGS_POP
    print(os.path.abspath("tags_pop.json"))
    try:
        with open("tags_pop.json", "r", encoding="utf-8") as file:
            TAGS_POP = json.load(file)
    except Exception as e:
        print("tags JSON loading exception: ", e)
load_tags_pop()

def score_post(user, tags, pop):

    exploration_mod = random.choices(
        [True, False],
        weights=[15, 85]
    )[0]

    score = 0
    unknown_tags = 0
    max_neg = 0

    for tag in tags:

        w = user.like_tags.get(tag, 0)

        score += w

        if tag not in user.like_tags:
            unknown_tags += 1

        if w < max_neg:
            max_neg = w

    score /= (len(tags) ** 0.5)

    pop_factor = 1 + 0.15 * math.log10(pop + 10)
    score *= pop_factor

    tag_count_factor = min(1.0, len(tags) / 25)
    score *= tag_count_factor

    if exploration_mod:
        unknown_ratio = unknown_tags / len(tags)
        score += unknown_ratio * 2

    return score

def pick_top_tag(user, k=10):
    top = sorted(user.like_tags.items(), key=lambda x: x[1], reverse=True)[:k]

    if not top:
        return None

    tags, scores = zip(*top)

    weights = [max(0.01, s) for s in scores]

    return random.choices(tags, weights=weights, k=1)[0]

def get_random_post(user):

    for i in range(5):

        query = build_query(user)
        print("QUERY:", query)

        if len(query.split()) >= 3:
            pid = random.randint(0, 20)
        else:
            pid = random.randint(0, 200)

        params = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "json": 1,
            "limit": 100,
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

            best_post = None
            for post in posts:
                if str(post["id"]) in user.posts_cache:
                    continue

                tags = post["tags"].split()
                score = score_post(user, tags, post["score"])

                post["tags_score"] = score

                if best_post == None or score > best_post["tags_score"]:
                    best_post = post
            return best_post

        except Exception as e:
            print(e)
            continue

    return None

def build_query(user):

    query = []

    positive_tags = {
        tag: score
        for tag, score in user.like_tags.items()
        if score > 0
    }

    negative_tags = {
        tag: score
        for tag, score in user.like_tags.items()
        if score < 0
    }

    if positive_tags:

        tags = list(positive_tags.keys())

        k = random.choices(
            [1, 2],
            weights=[85, 15]
        )[0]

        top_tags = sorted(
            positive_tags.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]

        weights = [
            score ** 0.5
            for _, score in top_tags
        ]

        selected_tags = random.choices(
            [tag for tag, _ in top_tags],
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

    if user.config["ai_filter"]:

        query.extend([
            "-ai_generated",
            "-stable_diffusion",
            "-midjourney",
            "-novelai",
            "-ia_generated"
        ])

    return " ".join(query)

def print_top_tags(user, limit=50):

    sorted_tags = sorted(
        user.like_tags.items(),
        key=lambda x: x[1],
        reverse=True
    )

    print("\n=== TAG SCORES ===\n")

    for i, (tag, score) in enumerate(sorted_tags[:limit], start=1):

        print(
            f"{i:02d}. "
            f"{tag:<35} "
            f"{score:.2f}"
        )

    print("\n=== MOST DISLIKED ===\n")

    disliked = sorted(
        user.like_tags.items(),
        key=lambda x: x[1]
    )

    for i, (tag, score) in enumerate(disliked[:limit], start=1):

        print(
            f"{i:02d}. "
            f"{tag:<35} "
            f"{score:.2f}"
        )

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

# ===== Settings =====

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

@dp.callback_query(F.data == "feed")
async def open_feed(callback: CallbackQuery):

    user = User(callback.from_user.id)

    post = get_random_post(user)
    if post == None:
        return
    
    user.posts_cache[str(post["id"])] = post

    if len(user.posts_cache) > 200:
        oldest_key = next(iter(user.posts_cache))
        del user.posts_cache[oldest_key] 

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

    user.save_user_data()

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
    tags = post["tags"].split()

    for tag in tags:
        if tag not in user.like_tags:
            user.like_tags[tag] = 0

        base = 1

        pop = TAGS_POP.get(tag, 1)
        tag_rarity = 1 / (math.log10(pop + 10) ** 2)
        tag_rarity = max(0.03, tag_rarity)

        base *= tag_rarity

        if "_" in tag:
            base *= 1.3

        if "(" in tag:
            base *= 1.8

        preference = 1 + 0.6 * math.tanh(user.like_tags[tag] / 5)

        factor = base * preference

        user.like_tags[tag] += factor

    user.save_user_data()

    print_top_tags(user)
    await callback.answer("Added to favorites")

@dp.callback_query(F.data.startswith("dislike:"))
async def dislike_post(callback: CallbackQuery):

    user = User(callback.from_user.id)

    isDisliked = int(callback.data.split(":")[1])
    if isDisliked:
        return

    post_id = callback.data.split(":")[2]

    print(post_id)

    await callback.message.edit_reply_markup(
        reply_markup=feed_keyboard(post_id, disliked=True)
    )

    post = user.posts_cache.get(post_id)
    tags = post["tags"].split()

    for tag in tags:
        if tag not in user.like_tags:
            user.like_tags[tag] = 0

        base = 1

        pop = TAGS_POP.get(tag, 1)
        tag_rarity = 1 / (math.log10(pop + 10) ** 2)
        tag_rarity = max(0.03, tag_rarity)

        base *= tag_rarity

        if "_" in tag:
            base *= 1.3

        if "(" in tag:
            base *= 1.8

        preference = 1 + 0.6 * math.tanh(-user.like_tags[tag] / 5)

        factor = base * preference

        user.like_tags[tag] -= factor

    user.save_user_data()

    print_top_tags(user)
    await callback.answer("Less like this")

# ===== Main =====

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())