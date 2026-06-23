import asyncio
import os
import random
from rule_34_client import R34_CLIENT

R34_API_KEY = os.getenv("R34_API_KEY")
R34_USER_ID = os.getenv("R34_USER_ID")

class Posts_poll:

    def __init__(self):
        self.pool = []
        self.pool_size = 0
        self.ids = set()

    async def init_pool(self):

        for i in range(0,100):
            try:
                print(f"\rLoading pool page {i}/100", end="", flush=True)
                params = {
                    "page": "dapi",
                    "s": "post",
                    "q": "index",
                    "json": 1,
                    "limit": 500,
                    "pid": i,
                    "tags": "score:>20",
                    "api_key": R34_API_KEY,
                    "user_id": R34_USER_ID
                }

                posts = await R34_CLIENT.search(params)

                if not isinstance(posts, list):
                    raise TypeError("Bad API response")

                if not posts:
                    continue

                for post in posts:

                    if post["id"] in self.ids:
                        continue
                    self.ids.add(post["id"])

                    tags = post["tags"].split(" ")
                    self.pool.append({
                        "preview_url": post["sample_url"],
                        "sample_url": post["sample_url"],
                        "file_url": post["file_url"],
                        "id": post["id"],
                        "score": post["score"],
                        "tags": tags
                    })
                    self.pool_size += 1

            except Exception as e:
                import traceback
                traceback.print_exc()

        print("Inited dayly post pool")

    async def refresh_pool_loop(self):

        while True:
            await asyncio.sleep(86400)

            await POSTS_POOL.init_pool()
            
    def get_random_post(self, limit=100):
        return random.sample(
            self.pool,
            min(limit, len(self.pool))
        )

POSTS_POOL: Posts_poll = Posts_poll()