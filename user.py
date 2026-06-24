import json
import math
import os
import random
from pathlib import Path
from clip import Clip
import torch
import aiohttp
import asyncio
from PIL import Image
from io import BytesIO
from subscription_manager import Subscription_manager
from posts_pool import POSTS_POOL

R34_API_KEY = os.getenv("R34_API_KEY")
print("R34_API_KEY: ", R34_API_KEY)
R34_USER_ID = os.getenv("R34_USER_ID")
print("R34_USER_ID: ", R34_USER_ID)
CLIP: Clip = Clip()

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
        self.json_path = f"users\\{self.id}.json"
        path = Path(self.json_path)
        if path.is_file():
            self.__load_json()
        else:
            self.__create_json()

    def __create_json(self):
        self.reactions = {}
        self.posts_cache = {}
        self.reaction_count = 0
        self.like_tensor = torch.zeros(512, dtype=torch.float32, device=CLIP.device)
        self.dislike_tensor = torch.zeros(512, dtype=torch.float32, device=CLIP.device)
        self.config = {
            "ai_filter": False
        }
        self.save_user_data()

    def __load_json(self):
        with open(self.json_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        self.reactions = data["reactions"]
        self.posts_cache = data["posts_cache"]
        self.config = data["config"]
        self.reaction_count = data["reaction_count"]
        self.like_tensor = torch.tensor(
            data["like_tensor"],
            dtype=torch.float32,
            device=CLIP.device
        )
        self.dislike_tensor = torch.tensor(
            data["dislike_tensor"],
            dtype=torch.float32,
            device=CLIP.device
        )
        self.sub_manager.load(data)
        
    def save_user_data(self):
        data = {
            "reactions": self.reactions,
            "posts_cache": self.posts_cache,
            "config": self.config,
            "reaction_count": self.reaction_count,
            "like_tensor": self.like_tensor.cpu().tolist(),
            "dislike_tensor": self.dislike_tensor.cpu().tolist()
        }
        data.update(self.sub_manager.get_data_for_save())
        with open(self.json_path, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=4
            )

    def update_posts_cache(self, post):
        self.posts_cache[str(post["id"])] = post

        if len(self.posts_cache) > 200:
            oldest_key = next(iter(self.posts_cache))
            del self.posts_cache[oldest_key]

        self.save_user_data()

    def __reaction(self, type, post):
        tags = post["tags"]

        self.print_tags_weight(max=-3)

        for tag in tags:
            if tag not in self.reactions:
                self.reactions[tag] = {
                    "dis": 0,
                    "like": 0,
                    "skip": 0
                }
            self.reactions[tag][type] += 1
            
        if type != "skip":
            self.reaction_count += 1

    def __update_like_tensor(self, post, alpha):

        imageTensor = CLIP.get_post_tensor(post)

        self.like_tensor = self.like_tensor * 0.95 + imageTensor.squeeze() * alpha

        self.like_tensor /= torch.norm(self.like_tensor)

    def __update_dislike_tensor(self, post, alpha):

        imageTensor = CLIP.get_post_tensor(post)

        self.dislike_tensor = self.dislike_tensor * 0.95 + imageTensor.squeeze() * alpha

        self.dislike_tensor /= torch.norm(self.dislike_tensor)

    def dislike_post(self, post):
        self.__reaction("dis", post)
        self.__update_dislike_tensor(post, 0.08)
        self.save_user_data()

    def like_post(self, post):
        self.__reaction("like", post)
        self.__update_like_tensor(post, 0.05)
        self.save_user_data()

    def skip_post(self, post):
        self.__reaction("skip", post)
        self.save_user_data()

    def __tag_weight(self, tag):

        stats = self.reactions.get(tag)

        if not stats:
            return 0

        likes = stats["like"]
        dislikes = stats["dis"]
        skips = stats["skip"]

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
    
    def __score_post(self, post):

        is_exploration_mod = True if random.random() < 0.15 else False

        tags = post["tags"]
        post_score = post["score"]

        score = 0

        known = 0
        unknown = 0

        for tag in tags:

            if tag in self.reactions:
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
    
    def __get_best_tags(self, limit=20):

        scored = []

        for tag in self.reactions:

            weight = self.__tag_weight(tag)

            if weight > 0:
                scored.append((tag, weight))

        scored.sort(
            key=lambda x: x[1],
            reverse=True
        )

        return scored[:limit]
    
    async def post_like_this(self, ref_post, loading_msg=None, current_loading_text=""):

        async def update_msg(text, points=3):
            text += points * "."
            nonlocal current_loading_text
            if (loading_msg is not None and current_loading_text != text):
                current_loading_text = text
                await loading_msg.edit_text(current_loading_text)

        await update_msg("🔄 Searching posts")

        posts = POSTS_POOL.get_random_post(1000)

        load_points = 0
        most_likeness = posts[0]
        most_likeness["likeness"] = 0

        ref_tags = set(ref_post["tags"])
        ref_embedding = CLIP.get_post_tensor(ref_post).squeeze(0)

        await update_msg("🔄 Similarity calculation")

        embeddings = torch.stack([
            CLIP.get_post_tensor(post).squeeze(0)
            for post in posts
        ])

        sims = embeddings @ ref_embedding

        for i, post in enumerate(posts):
            if i % 50 == 0:
                load_points += 1
                await update_msg("🔄 Ranking posts", load_points)
                if load_points == 3:
                    load_points = 1

            post["likeness"] = 0
            for tag in post["tags"]:
                if tag in ref_tags:

                    pop = TAGS_POP.get(tag, 100)
                    rarity = 1 / math.log10(pop + 10)
                    rarity = max(0.15, rarity)

                    post["likeness"] += 1 * rarity

            post["likeness"] += sims[i].item() * 10

            if post["likeness"] > most_likeness["likeness"]:
                most_likeness = post

        return most_likeness

    async def next_post(self, loading_msg=None, current_loading_text=""):

        async def update_msg(text, points=3):
            text += points * "."
            nonlocal current_loading_text
            if (loading_msg is not None and current_loading_text != text):
                current_loading_text = text
                await loading_msg.edit_text(current_loading_text)

        await update_msg("🔄 Searching")

        posts = POSTS_POOL.get_random_post(
            500 if self.sub_manager.is_premium() else 100
        )

        try:
            await update_msg("🔄 Ranking posts")

            scored_posts = []

            for post in posts:
                if str(post["id"]) in self.posts_cache:
                    continue

                score = self.__score_post(post)

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
            await self.__calculate_similarities(best_posts)
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

    def print_tags_weight(self, min = -999, max = 999):
        weights = {}

        for tag in self.reactions.keys():
            w = self.__tag_weight(tag)
            if w >= min or w <= max:
                weights[tag] = w

        sorted_by_val = dict(sorted(weights.items(), key=lambda x: x[1]))
        
        for tag in sorted_by_val.keys():
            print(f"Weight of the \"{tag}\": ", weights[tag])

    async def __calculate_similarities(self, posts):

        embeddings = []

        for post in posts:

            tensor = CLIP.get_post_tensor(post)

            if tensor is None:
                continue

            embeddings.append(tensor.squeeze(0))

        if not embeddings:
            return

        embeddings = torch.stack(embeddings)

        pos_similarities = embeddings @ self.like_tensor
        neg_similarities = embeddings @ self.dislike_tensor

        for post, pos_sim, neg_sim in zip(
            posts,
            pos_similarities,
            neg_similarities
        ):
            post["similarity"] = (
                pos_sim.item()
                - neg_sim.item() * 0.5
            ) * CLIP_WEIGHT