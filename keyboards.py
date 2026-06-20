from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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

def feed_keyboard(post_id, liked=False, disliked=False):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❤️ Liked" if liked else "🤍 Like",
                    callback_data=f"like:{1 if liked else 0}:{post_id}"
                ),
                InlineKeyboardButton(
                    text="Skip",
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

def premium_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐ Premium — 30 days",
                    callback_data="buy_premium"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅ Back",
                    callback_data="main_menu"
                )
            ]
        ]
    )