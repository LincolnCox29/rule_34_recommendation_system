from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton

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
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Buy ⭐ Premium",
                    callback_data="premium_promotion"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Feedback",
                    callback_data="feedback"
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
                    text="⬅ Back",
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
                    text="⬅ Back",
                    callback_data="main_menu"
                )
            ]
        ]
    )

def premium_keyboard():

    def price_button(price, duration) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            text=f"⭐{duration} days — {price} stars⭐",
            callback_data=f"buy_premium:{price}:{duration}"
        )


    return InlineKeyboardMarkup(
        inline_keyboard=[
            [price_button(250, 30)],
            [price_button(150, 15)],
            [price_button(100, 7)],
            [price_button(20, 1)],
            [
                InlineKeyboardButton(
                    text="⬅ Back",
                    callback_data="main_menu"
                )
            ]
        ]
    )

def feedback_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🐙 GitHub — LincolnCox29",
                    url="https://github.com/LincolnCox29"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎮 Discord — nenko_",
                    url="https://discord.com/users/697426221532708865"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📧 Email — deortias29@gmail.com",
                    copy_text=CopyTextButton(
                        text="deortias29@gmail.com"
                    )
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