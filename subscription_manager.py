import time
import os
from data_base import DB

FREE_POSTS_PER_DAY = 5
DAY = 86400

ENDLESS_SUBS = []

class Subscription_manager:

    def __init__(self, user_id):
        self.id = user_id

        if not ENDLESS_SUBS:
            self.__get_endless_subs()

        self.subscription_end = DB.get_sub_end(self.id)

    def __get_endless_subs(self):
        global ENDLESS_SUBS

        string = os.getenv("ENDLESS_SUBS", "")
        ENDLESS_SUBS = string.split(",")

    def is_premium(self) -> bool:
        return (
            time.time() < self.subscription_end
            or str(self.id) in ENDLESS_SUBS
        )

    def add_subscription_days(self, days: int):

        now = time.time()

        if self.subscription_end < now:
            self.subscription_end = now

        self.subscription_end += days * DAY

        DB.update_sub_end(
            self.id,
            self.subscription_end
        )

        DB.commit()

    def reload_daily_limit(self):

        now = time.time()

        reload_time = DB.get_today_posts_counter_reload_time(
            self.id
        )

        if reload_time is None:
            reload_time = 0

        if now >= reload_time:

            DB.set_today_posts_counter(
                self.id,
                0
            )

            DB.set_today_posts_counter_reload_time(
                self.id,
                now + DAY
            )

            DB.commit()

    def can_view_post(self) -> bool:

        if self.is_premium():
            return True

        self.reload_daily_limit()

        counter = DB.get_today_posts_counter(
            self.id
        )

        return counter < FREE_POSTS_PER_DAY

    def register_post_view(self):

        if self.is_premium():
            return

        self.reload_daily_limit()

        counter = DB.get_today_posts_counter(
            self.id
        )

        DB.set_today_posts_counter(
            self.id,
            counter + 1
        )

        print("COUNTER =", counter)

        DB.commit()