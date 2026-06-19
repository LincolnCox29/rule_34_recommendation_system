import time

FREE_POSTS_PER_DAY = 100
DAY = 86400

class Subscription_manager:

    def __init__(self):

        self.subscription_end = 0.0
        self.today_posts_counter = 0
        self.today_posts_counter_reload_time = 0

    def is_premium(self) -> bool:
        return time.time() < self.subscription_end
    
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

        return self.today_posts_counter < self.FREE_POSTS_PER_DAY
    
    def register_post_view(self):

        self.reload_daily_limit()

        if not self.is_premium():
            self.today_posts_counter += 1