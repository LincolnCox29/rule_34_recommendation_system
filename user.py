import json
import math
import os
import random
import torch
import aiohttp
import asyncio
from PIL import Image
from io import BytesIO
from subscription_manager import Subscription_manager
from data_base import DB
from clip import CLIP
from rule_34_client import R34_CLIENT
from urllib.parse import urlparse

R34_API_KEY = os.getenv("R34_API_KEY")
print("R34_API_KEY: ", R34_API_KEY)
R34_USER_ID = os.getenv("R34_USER_ID")
print("R34_USER_ID: ", R34_USER_ID)

CLIP_WEIGHT = 4.0

TAGS_POP = None
def load_tags_pop():
    global TAGS_POP
    print("Tags pop json path: ", os.path.abspath("tags_pop.json"))
    try:
        with open("tags_pop.json", "r", encoding="utf-8") as file:
            TAGS_POP = json.load(file)
    except Exception as e:
        print("tags JSON loading exception: ", e)
load_tags_pop()

class User:

    def __init__(self, id, r34_client):
        self.r34_client = r34_client
        self.id = id
        self.sub_manager = Subscription_manager(id)
        self.posts_ids_cache = []
        self.last_post = None
        DB.create_user(self.id)
        USERS[id] = self

    def update_posts_cache(self, post):
        self.posts_ids_cache.append(int(post["id"]))

        if len(self.posts_ids_cache) > 100:
            self.posts_ids_cache.pop(0)

    def __reaction(self, type, post):
        tags = post["tags"].split()

        for tag in tags:
            DB.create_tag(tag, self.id)
            DB.reaction_on_tag(tag, self.id, type)
            
        if type != "skip":
            DB.inc_reaction_counter(self.id)

    def __update_tensor(self, post, alpha, tensor_type):
        imageTensor = CLIP.get_post_tensor(post)
        
        tensor = DB.get_user_tensor(self.id, tensor_type)

        tensor = tensor * 0.95 + imageTensor.squeeze() * alpha
        tensor /= torch.norm(tensor)

        DB.update_user_tensor(self.id, tensor, tensor_type)

    def dislike_post(self, post):
        self.__reaction("dislikes", post)
        self.__update_tensor(post, 0.08, "dislike")
        DB.commit()

    def like_post(self, post):
        self.__reaction("likes", post)
        self.__update_tensor(post, 0.05, "like")
        DB.commit()

    def skip_post(self, post):
        self.__reaction("skips", post)
        DB.commit()

    def __tag_weight(self, tag):

        stats = DB.get_tag_stats(tag, self.id)

        if not stats:
            return 0

        likes, dislikes, skips = stats

        seen = likes + dislikes + skips

        if seen == 0:
            return 0

        preference = (
            likes
            - dislikes * 2
            - skips * 0.15
        ) / seen

        confidence = min(1.0, seen / 10)

        pop = TAGS_POP.get(tag, 100)

        rarity = 1 / math.log10(pop + 10)

        rarity = max(0.15, rarity)

        weight = preference * confidence * rarity * 20

        return weight
    
    def __score_post(self, post, user_tags):

        file_url = post.get("file_url", "").lower()
        path = urlparse(file_url).path

        if not path.endswith((".jpg", ".jpeg", ".png")):
            return -10000

        is_exploration_mod = True if random.random() < 0.15 else False

        tags = post["tags"].split()
        post_score = post["score"]

        score = 0

        known = 0
        unknown = 0

        for tag in tags:

            if tag in user_tags:
                known += 1
            else:
                unknown += 1

            w = self.__tag_weight(tag)

            score += w

        score /= max(1, len(tags) ** 0.5)

        quality_factor = min(
            1.5,
            1 + math.log10(post_score + 10) * 0.15
        )

        score *= quality_factor

        tag_factor = min(
            1.0,
            len(tags) / 20
        )

        score *= tag_factor

        if random.random() < 0.15:
            score += unknown * 0.25

        if is_exploration_mod:
            unknown_ratio = unknown / len(tags)
            score += unknown_ratio * 2

        return score
    
    def __get_best_tags(self, user_tags, limit=20):

        scored = []

        for tag in user_tags:

            weight = self.__tag_weight(tag)

            if weight > 0:
                scored.append((tag, weight))

        scored.sort(
            key=lambda x: x[1],
            reverse=True
        )

        return scored[:limit]
    
    def __get_worst_tags(self, user_tags, limit=20):
        scored = []

        for tag in user_tags:

            weight = self.__tag_weight(tag)

            if weight < 0:
                scored.append((tag, weight))

        scored.sort(
            key=lambda x: x[1],
            reverse=False
        )

        return scored[:limit]

    
    def __build_query(self, user_tags):

        query = []

        best_tags = self.__get_best_tags(user_tags)

        if best_tags:

            tags = [tag for tag, _ in best_tags]

            weights = [weight for _, weight in best_tags]

            positive_count = random.choices(
                [1, 2],
                weights=[80, 20]
            )[0]

            selected = random.choices(
                tags,
                weights=weights,
                k=positive_count
            )

            query.extend(set(selected))

        worst_tags = self.__get_worst_tags(user_tags, 3)

        if worst_tags:
            query.extend(
                f"-{tag}"
                for tag, _ in worst_tags[:10]
            )

        if DB.get_user_ai_filter(self.id):
            query.extend([
                "-ai_generated",
                "-stable_diffusion",
                "-midjourney",
                "-novelai",
                "-ia_generated"
            ])

        return " ".join(query)
    
    async def next_post(self, loading_msg=None, current_loading_text=""):

        async def update_msg(text, points=3):
            text += points * "."
            nonlocal current_loading_text
            if (loading_msg is not None and current_loading_text != text):
                current_loading_text = text
                await loading_msg.edit_text(current_loading_text)

        await update_msg("🔄 Building query")

        user_tags = DB.get_user_tags(self.id)

        for i in range(5):

            if i < 4:
                query = self.__build_query(user_tags)
            elif DB.get_user_ai_filter(self.id):
                query = []
                query = (
                    "-ai_generated " +
                    "-stable_diffusion " +
                    "-midjourney " +
                    "-novelai " +
                    "-ia_generated"
                )
            print("QUERY:", query)

            await update_msg("🔄 Searching", points=i if i < 4 else 3)

            pid = random.randint(0, 100)

            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "limit": 200 if self.sub_manager.is_premium() else 100,
                "pid": pid,
                "tags": query + " score:>20",
                "api_key": R34_API_KEY,
                "user_id": R34_USER_ID
            }

            try:

                posts = await self.r34_client.search(params)

                if not isinstance(posts, list):
                    raise TypeError("Bad API response")

                if not posts:
                    continue

                scored_posts = []

                await update_msg("🔄 Ranking posts")

                for post in posts:
                    if int(post["id"]) in self.posts_ids_cache:
                        continue

                    score = self.__score_post(post, user_tags)

                    post["user_score"] = score
                    scored_posts.append(post)

                scored_posts.sort(
                    key=lambda p: p["user_score"],
                    reverse=True
                )

                await update_msg("🔄 Finding best post")

                best_posts = scored_posts[:10]

                best_post = await self.__get_best_post(best_posts)

                self.sub_manager.register_post_view()

                await loading_msg.delete()

                return best_post

            except Exception as e:
                import traceback
                traceback.print_exc()

        return None
    
    async def __get_best_post(self, best_posts):

        ranging = None
        if self.sub_manager.is_premium():
            await self.__get_post_tensor_batch(best_posts)
            ranging = lambda post, best_post: (
                best_post is None
                or post["user_score"] + post["similarity"] >
                best_post["user_score"] + best_post.get("similarity", 0)
            )
        else:
            ranging = lambda post, best_post: (
                best_post is None
                or post["user_score"] > best_post["user_score"]
            )

        best_post = None
        for post in best_posts:
            if (ranging(post, best_post)):
                best_post = post
        return best_post

    async def __session_download_image(self, session, url):
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None

                data = await response.read()
                return Image.open(BytesIO(data)).convert("RGB")

        except Exception:
            return None

    async def __get_post_tensor_batch(self, posts):

        urls = [
            (
                post.get("preview_url")
                or post.get("sample_url")
                or post.get("file_url")
            )
            for post in posts
        ]

        connector = aiohttp.TCPConnector(limit=10)

        async with aiohttp.ClientSession(
            connector=connector,
            headers={"User-Agent": "Mozilla/5.0"}
        ) as session:

            images = await asyncio.gather(*[
                self.__session_download_image(session, url)
                for url in urls
            ])

        valid_images = []
        valid_posts = []

        for post, img in zip(posts, images):
            if img is not None:
                valid_images.append(img)
                valid_posts.append(post)

        if not valid_images:
            return

        batch = torch.stack([
            CLIP.preprocess(img)
            for img in valid_images
        ]).to(CLIP.device)

        with torch.no_grad():

            embeddings = CLIP.model.encode_image(batch)

            embeddings = embeddings / embeddings.norm(
                dim=-1,
                keepdim=True
            )

            pos_similarities = embeddings @ DB.get_user_tensor(self.id, "like")

            neg_similarities = embeddings @ DB.get_user_tensor(self.id, "dislike")

        for post, pos_sim, neg_sim in zip(valid_posts, pos_similarities, neg_similarities):
            post["similarity"] = (
                pos_sim.item()
                - neg_sim.item() * 0.5
            ) * CLIP_WEIGHT

USERS = {}

def get_user_cache(id):

    user = USERS.get(id)

    if user is None:
        user = User(id, R34_CLIENT)

    return user