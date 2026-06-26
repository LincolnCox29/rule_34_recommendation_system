import time
import os

FREE_POSTS_PER_DAY = 30
DAY = 86400
ENDLESS_SUBS = []

class Subscription_manager:

    def __init__(self, id):
        self.id = id
        if ENDLESS_SUBS == []:
            self.__get_endless_subs()
        self.subscription_end = 0.0
        self.today_posts_counter = 0
        self.today_posts_counter_reload_time = 0

    def get_data_for_save(self):
        return {
            "subscription_end": self.subscription_end,
            "today_posts_counter": self.today_posts_counter,
            "today_posts_counter_reload_time": self.today_posts_counter_reload_time
        }

    def load(self, json_data):
        self.subscription_end = json_data["subscription_end"]
        self.today_posts_counter = json_data["today_posts_counter"]
        self.today_posts_counter_reload_time = json_data["today_posts_counter_reload_time"]

    def is_premium(self) -> bool:
        return (
            (time.time() < self.subscription_end) or
            (str(self.id) in ENDLESS_SUBS)
        )
    
    def __get_endless_subs(self):
        global ENDLESS_SUBS
        string = os.getenv("ENDLESS_SUBS")
        ENDLESS_SUBS = string.split(",")
    
    def add_subscription_days(self, days: int):

        now = time.time()

        if self.subscription_end < now:
            self.subscription_end = now

        self.subscription_end += days * DAY

    def reload_daily_limit(self):

        now = time.time()

        if now >= self.today_posts_counter_reload_time:
            self.today_posts_counter = 0
            self.today_posts_counter_reload_time = now + DAY

    def can_view_post(self) -> bool:

        self.reload_daily_limit()

        if self.is_premium():
            return True

        return self.today_posts_counter < FREE_POSTS_PER_DAY
    
    def register_post_view(self):

        self.reload_daily_limit()

        if not self.is_premium():
            self.today_posts_counter += 1

    def get_sub_expire_str(self):
        remaining = int(self.subscription_end - time.time())

        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        minutes = (remaining % 3600) // 60

        return f"{days} d. {hours} h. {minutes} min."