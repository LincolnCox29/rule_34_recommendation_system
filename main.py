import asyncio
from dotenv import load_dotenv
import os
from user import User, get_user_cache
import torch
import keyboards
from rule_34_client import R34_CLIENT
from data_base import DB

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery
)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

R34_API_KEY = os.getenv("R34_API_KEY")
R34_USER_ID = os.getenv("R34_USER_ID")

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):

    await callback.message.answer(
        "Choose action:",
        reply_markup=keyboards.main_menu()
    )

    await callback.answer()

@dp.callback_query(F.data == "turn_AI_filter")
async def turn_AI_filter(callback: CallbackQuery):

    user = get_user_cache(callback.from_user.id)

    DB.turn_user_ai_filter(user.id)

    await callback.message.edit_text(
        "Settings",
        reply_markup=keyboards.settings_menu(user)
    )

    user.save_user_data()

    await callback.answer()

@dp.callback_query(F.data == "settings")
async def settings(callback: CallbackQuery):

    user = get_user_cache(callback.from_user.id)

    await callback.message.edit_text(
        "Settings",
        reply_markup=keyboards.settings_menu(user)
    )

    await callback.answer()

# ===== Start =====

@dp.message(F.text == "/start")
async def start(message: Message):

    await message.answer(
        "Choose action:",
        reply_markup=keyboards.main_menu()
    )

# ===== Open Feed =====

@dp.callback_query(F.data.startswith("to_feed"))
async def open_feed(callback: CallbackQuery):

    user = get_user_cache(callback.from_user.id)

    #DB.dump_user_to_file(user.id)

    if not await check_limit(callback, user):
        return

    data = callback.data
    if ":" in data and "to_feed" in data:
        post_id = data.split(":")[1]
        post = user.last_post

        if int(post_id) in user.posts_ids_cache:
            await callback.message.edit_reply_markup(
                reply_markup=None
            )
            user.skip_post(post)
        

    loading_msg = await callback.message.answer("🔄 Loading...")
    post = await user.next_post(loading_msg)
    if post == None:
        return

    user.last_post = post

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
        reply_markup=keyboards.feed_keyboard(str(post["id"]))
    )

    await callback.answer()

# ===== Like =====

@dp.callback_query(F.data.startswith("like:"))
async def like_post(callback: CallbackQuery):

    user = get_user_cache(callback.from_user.id)

    if not await check_limit(callback, user):
        return

    isLiked = int(callback.data.split(":")[1])
    if isLiked:
        return

    post_id = callback.data.split(":")[2]

    print(post_id)

    await callback.message.edit_reply_markup(
        reply_markup=keyboards.feed_keyboard(post_id, liked=True)
    )

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    user.like_post(user.last_post)

    await callback.answer("Added to favorites")

    await open_feed(callback)

@dp.callback_query(F.data.startswith("dislike:"))
async def dislike_post_ui(callback: CallbackQuery):

    user = get_user_cache(callback.from_user.id)

    if not await check_limit(callback, user):
        return

    isDisliked = int(callback.data.split(":")[1])
    if isDisliked:
        return

    post_id = callback.data.split(":")[2]

    print("disliked: ", post_id)

    await callback.message.edit_reply_markup(
        reply_markup=keyboards.feed_keyboard(post_id, disliked=True)
    )

    user.dislike_post(user.last_post)

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.answer("Less like this")

    await open_feed(callback)

async def check_limit(callback: CallbackQuery, user: User):
    if user.sub_manager.can_view_post():
        await callback.answer()
        return True

    await callback.message.answer(
        "🚫 Daily free limit reached.\n\n"
        "You've used all free posts available today.\n\n"
        "⭐ Premium unlocks:\n"
        "- Unlimited feed\n"
        "- AI image recommendations (CLIP)\n"
        "- Better post ranking\n"
        "- Faster discovery of new content\n"
        "- No daily limits\n"
        "- Support for the author\n\n"
        "Choose a plan:",
        reply_markup=keyboards.premium_keyboard()
    )

    await callback.answer()

    return False

@dp.callback_query(F.data == "premium_promotion")
async def premium_promotion(callback: CallbackQuery):
    await callback.message.answer(
        "⭐ Premium unlocks:\n"
        "- Unlimited feed\n"
        "- AI image recommendations (CLIP)\n"
        "- Better post ranking\n"
        "- Faster discovery of new content\n"
        "- No daily limits\n"
        "- Support for the author\n\n"
        "Choose a plan:",
        reply_markup=keyboards.premium_keyboard()
    )

@dp.callback_query(F.data == "feedback")
async def feedback_ui(callback: CallbackQuery):
    await callback.message.answer(
        "👋 About the author (LincolnCox29)\n\n"
        "Thanks for using my tg bot!\n\n"
        "If you have suggestions, bug reports, partnership offers, or just want to get in touch, use the links below. ↓",
        reply_markup=keyboards.feedback_menu()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_premium"))
async def buy_premium(callback: CallbackQuery):

    data = callback.data
    price = data.split(":")[1]
    duration = data.split(":")[2]

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Premium Subscription",
        description=f"{duration} days of Premium access",
        payload=f"premium_{duration}",
        currency="XTR",
        prices=[
            LabeledPrice(
                label=f"Premium {duration} days",
                amount=price
            )
        ]
    )

    await callback.answer()

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(
        pre_checkout_query.id,
        ok=True
    )

@dp.message(F.successful_payment)
async def successful_payment(message: Message):

    user = get_user_cache(message.from_user.id)

    payment = message.successful_payment

    days = int(payment.invoice_payload.split("_")[1])

    user.sub_manager.add_subscription_days(days)

    user.save_user_data()

    await message.answer(
        f"✅ Premium activated for {days} days!\n\n"
        "Choose action:",
        reply_markup=keyboards.main_menu()
    )



# ===== Main =====

def machine_configuration():
    print("Torch:", torch.__version__)
    print("CUDA:", torch.version.cuda)
    print("Available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))

async def main():
    machine_configuration()
    await R34_CLIENT.start()
    try:
        await dp.start_polling(bot)
    finally:
        await R34_CLIENT.close()
        DB.close()

if __name__ == "__main__":
    asyncio.run(main())