import asyncio
from io import BytesIO
import os
import random
import time
from PIL import Image

import aiohttp
import torch
from rule_34_client import R34_CLIENT
from clip import CLIP

R34_API_KEY = os.getenv("R34_API_KEY")
R34_USER_ID = os.getenv("R34_USER_ID")

class Posts_poll:

    def __init__(self):
        self.pool = []
        self.pool_size = 0
        self.ids = set()
        self.download_semaphore = asyncio.Semaphore(8)

    async def init_pool(self):

        for i in range(0,5):
            try:
                print(f"\rLoading pool page {i+1}/100", end="", flush=True)
                params = {
                    "page": "dapi",
                    "s": "post",
                    "q": "index",
                    "json": 1,
                    "limit": 300,
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

        print("\nLoading pool page: DONE")

        lead_time = 0.0
        for i in range(0, len(self.pool), 64):

            start = time.perf_counter()

            chunk = self.pool[i:i+64]
            await self.__calculate_embeddings(chunk)

            lead_time += time.perf_counter() - start

            print(f"\rСalculate pool embeddings [min: {(lead_time/60):.2f}]", end="", flush=True)
        print("\nСalculate pool embeddings: DONE")

        without_embeddings = sum(
            1 for p in self.pool
            if "embedding" not in p
        )

        print(
            f"Posts without embeddings: {without_embeddings}/{self.pool_size}"
        )

    async def __download_image(self, session, url):

        async with self.download_semaphore:

            for attempt in range(5):

                try:

                    async with session.get(
                        url,
                        timeout=20
                    ) as resp:

                        if resp.status == 200:

                            data = await resp.read()

                            return Image.open(
                                BytesIO(data)
                            ).convert("RGB")

                except Exception:
                    pass

                await asyncio.sleep(2)

        return None
        
    async def __load_images(self, posts):

        async with aiohttp.ClientSession() as session:

            tasks = [
                self.__download_image(
                    session,
                    post["preview_url"]
                )
                for post in posts
            ]

            images = await asyncio.gather(*tasks)

        valid_posts = []
        valid_images = []

        for post, image in zip(posts, images):

            if image is None:
                continue

            valid_posts.append(post)
            valid_images.append(image)

        return valid_posts, valid_images
    
    async def __calculate_embeddings(self, posts):

        posts, images = await self.__load_images(posts)

        if not images:
            return

        batch = torch.stack([
            CLIP.preprocess(img)
            for img in images
        ]).to(CLIP.device)

        with torch.no_grad():

            embeddings = CLIP.model.encode_image(batch)

            embeddings /= embeddings.norm(
                dim=-1,
                keepdim=True
            )

        for post, emb in zip(posts, embeddings):

            post["embedding"] = emb.cpu()

    async def refresh_pool_loop(self):

        while True:
            await asyncio.sleep(86400)

            await POSTS_POOL.init_pool()
            
    def get_random_post(self, limit=100, excluded_tags=None):

        excluded_tags = set(excluded_tags or [])

        filtered_pool = [
            post for post in self.pool
            if not excluded_tags.intersection(post["tags"])
        ]

        return random.sample(
            filtered_pool,
            min(limit, len(filtered_pool))
        )

POSTS_POOL: Posts_poll = Posts_poll()