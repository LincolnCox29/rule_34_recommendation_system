import json
import math
import os
import random
from pathlib import Path
import shutil
import time
import torch
from subscription_manager import Subscription_manager
from posts_pool import POSTS_POOL
from rule_34_client import R34_CLIENT
from clip import CLIP
import heapq

R34_API_KEY = os.getenv("R34_API_KEY")
print("R34_API_KEY: ", R34_API_KEY)
R34_USER_ID = os.getenv("R34_USER_ID")
print("R34_USER_ID: ", R34_USER_ID)

AI_TAGS = [
    "ai_generated",
    "stable diffusion",
    "ai",
    "ai assisted"
]

POST_LIKE_THIS_TAGS_CNT = 10000
POST_LIKE_THIS_CLIP_CNT = 500

NEXT_POST_TAGS_CNT = 3000
NEXT_POST_SUB_TAGS_CNT = 10000
NEXT_POST_CLIP_CNT = 1000

DISLIKE_WEIGHT = 8

LIKED_POSTS_MEM = 30
DISLIKED_POSTS_MEM = 15

CLIP_WEIGHT = 6.0

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
        self.posts_cache = {}
        self.sub_manager = Subscription_manager(id)
        self.json_path = Path("users") / f"{self.id}.json"
        self.tmp_path = f"{self.json_path}.tmp"
        self.bak_path = f"{self.json_path}.bak"
        path = Path(self.json_path)
        if path.is_file():
            self.__load_json()
        else:
            self.__create_json()

    def __create_json(self):
        self.reactions = {}
        self.viewed_post_ids = []
        self.liked_posts = []
        self.disliked_posts = []
        self.reaction_count = 0

        self.config = {
            "ai_filter": False
        }

        self.save_user_data()

    def __load_json(self):
        try:
            with open(self.json_path, "r", encoding="utf-8") as file:
                data = json.load(file)

        except Exception as e:
            print(f"JSON with user id {self.id} was corrupted. Load backup: {e}")

            try:
                shutil.copy2(self.bak_path, self.json_path)
                self.__load_json()
            except Exception as e:
                print(f"Backup with user id {self.id} also corrupted: {e}")
                self.__create_json()
            return

        self.reactions = data["reactions"]
        self.viewed_post_ids = data.get("viewed_post_ids", [])
        self.config = data["config"]
        self.reaction_count = data["reaction_count"]

        self.liked_posts = data.get("liked_posts", [])
        self.disliked_posts = data.get("disliked_posts", [])

        for post in self.liked_posts + self.disliked_posts:   
            if "embedding" in post:
                post["embedding"] = torch.tensor(
                    post["embedding"],
                    dtype=torch.float32,
                    device=CLIP.device
                )

        self.sub_manager.load(data)
        
    def save_user_data(self):

        def posts_to_snapshots(posts):
            
            snapshots = []

            for post in posts:

                snapshot = self.__make_post_snapshot(post)

                if "embedding" in snapshot:
                    snapshot["embedding"] = (
                        snapshot["embedding"]
                        .cpu()
                        .tolist()
                    )

                snapshots.append(snapshot)
            
            return snapshots

        liked_posts = posts_to_snapshots(self.liked_posts)
        disliked_posts = posts_to_snapshots(self.disliked_posts)

        data = {
            "reactions": self.reactions,
            "config": self.config,
            "reaction_count": self.reaction_count,
            "viewed_post_ids": self.viewed_post_ids,
            "liked_posts": liked_posts,
            "disliked_posts": disliked_posts 
        }

        data.update(self.sub_manager.get_data_for_save())

        try:

            if os.path.exists(self.json_path):
                shutil.copy2(self.json_path, self.bak_path)

            with open(self.tmp_path, "w", encoding="utf-8") as file:
                json.dump(
                    data,
                    file,
                    ensure_ascii=False,
                    indent=4
                )

        except Exception:
            print(f"Save denied to corrupted json with user id {self.id}")
            return

        os.replace(self.tmp_path, self.json_path)

    def update_posts_cache(self, post):
        self.posts_cache[str(post["id"])] = post
        self.viewed_post_ids.append(int(post["id"]))

        if len(self.posts_cache) > 200:
            oldest_key = next(iter(self.posts_cache))
            del self.posts_cache[oldest_key]

        if len(self.viewed_post_ids) > 1000:
            self.viewed_post_ids.pop(0)

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

    def dislike_post(self, post):
        self.__reaction("dis", post)

        self.disliked_posts.append(
            self.__make_post_snapshot(post)
        )

        while len(self.disliked_posts) > DISLIKED_POSTS_MEM:
            self.disliked_posts.pop(0)

        self.save_user_data()

    def like_post(self, post):

        self.__reaction("like", post)

        self.liked_posts.append(
            self.__make_post_snapshot(post)
        )

        while len(self.liked_posts) > LIKED_POSTS_MEM:
            self.liked_posts.pop(0)

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

        if post["id"] in self.viewed_post_ids:
            score *= 0.1

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

        return [tag for tag, _ in scored[:limit]]
    
    async def post_like_this(self, ref_post, loading_msg=None, current_loading_text=""):

        async def update_msg(text, points=3):
            text += points * "."
            nonlocal current_loading_text
            if (loading_msg is not None and current_loading_text != text):
                current_loading_text = text
                await loading_msg.edit_text(current_loading_text)

        await update_msg("🔄 Searching posts")

        posts = POSTS_POOL.get_random_post(
            POST_LIKE_THIS_TAGS_CNT,
            excluded_tags= AI_TAGS if self.config["ai_filter"] else None
        )

        load_points = 0

        ref_tags = set(ref_post["tags"])
        viewed_post_ids_set = set(self.viewed_post_ids)
        ref_embedding = CLIP.get_post_tensor(ref_post).squeeze(0)

        await update_msg("🔄 Similarity calculation")

        iteration_time: float = 0
        for post in posts:
            start_time = time.time()
            if iteration_time > 1.5:
                iteration_time = 0
                load_points += 1
                await update_msg("🔄 Ranking posts", load_points)
                if load_points == 3:
                    load_points = 0

            likeness = 0

            if int(post["id"]) in viewed_post_ids_set:
                post["likeness"] = likeness
                continue

            for tag in post["tags"]:
                if tag in ref_tags:
                    likeness += 1
                else:
                    likeness -= 0.1
            post["likeness"] = likeness
            end_time = time.time()
            iteration_time += end_time - start_time

        top_posts = heapq.nlargest(
            POST_LIKE_THIS_CLIP_CNT,
            posts,
            key=lambda p: p["likeness"]
        )

        await update_msg("🔄 Load embeddings")
        embeddings = torch.stack([
            CLIP.get_post_tensor(post).squeeze(0)
            for post in top_posts
        ])
        sims = embeddings @ ref_embedding

        most_likeness = None
        await update_msg("🔄 Finding best post")
        for i, post in enumerate(top_posts):
            if sims[i].item() > 0.98:
                continue

            tag_score = post["likeness"]
            clip_score = sims[i].item()

            post["likeness"] = (
                tag_score * 0.6 +
                clip_score * 8
            )

            if (most_likeness is None 
                or post["likeness"] > most_likeness["likeness"]):
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
            NEXT_POST_SUB_TAGS_CNT if self.sub_manager.is_premium() else NEXT_POST_TAGS_CNT,
            excluded_tags= AI_TAGS if self.config["ai_filter"] else None
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

            best_posts = scored_posts[:NEXT_POST_CLIP_CNT]

            best_post = await self.__get_best_post(best_posts)

            self.sub_manager.register_post_view()

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
                or post["user_score"] + post["like_similarity"] - post["dislike_similarity"] * 2 >
                best_post["user_score"] + best_post.get("like_similarity", 0) - best_post.get("dislike_similarity", 0) * 2 
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

        for post in posts:
            post["like_similarity"] = 0
            post["dislike_similarity"] = 0

        if not self.liked_posts:
            return

        post_embeddings = []
        valid_posts = []

        for post in posts:

            emb = CLIP.get_post_tensor(post)

            if emb is None:
                continue

            post_embeddings.append(emb.squeeze(0))
            valid_posts.append(post)

        if not post_embeddings:
            return

        liked_embeddings = torch.stack([
            post["embedding"]
            for post in self.liked_posts
        ])
        disliked_embeddings = torch.stack([
            post["embedding"]
            for post in self.disliked_posts
        ])

        post_embeddings = torch.stack(post_embeddings)

        like_similarities = post_embeddings @ liked_embeddings.T
        dislike_similarities = post_embeddings @ disliked_embeddings.T

        max_like_similarity = like_similarities.max(dim=1).values
        max_dislike_similarity = dislike_similarities.max(dim=1).values

        for post, sim in zip(valid_posts, max_like_similarity):
            post["like_similarity"] = sim.item() * CLIP_WEIGHT
        for post, sim in zip(valid_posts, max_dislike_similarity):
            post["dislike_similarity"] = sim.item() * CLIP_WEIGHT

    def __make_post_snapshot(self, post):

        snapshot = {
            "preview_url": post["preview_url"],
            "sample_url": post["sample_url"],
            "file_url": post["file_url"],
            "id": post["id"],
            "score": post["score"],
            "tags": post["tags"],
        }

        if "embedding" in post:
            snapshot["embedding"] = post["embedding"].clone()

        return snapshot
    
    async def get_next_post(self, like_this=None, loading_msg=None, current_loading_text=""):

        async def update_msg(text, points=3):
            text += points * "."
            nonlocal current_loading_text
            if (loading_msg is not None and current_loading_text != text):
                current_loading_text = text
                await loading_msg.edit_text(current_loading_text)

        await update_msg("🔄 Searching")

        posts = POSTS_POOL.get_random_post(
            NEXT_POST_SUB_TAGS_CNT if self.sub_manager.is_premium() else NEXT_POST_TAGS_CNT,
            excluded_tags= AI_TAGS if self.config["ai_filter"] else None
        )

        if like_this == None:
            like_this = random.choices(
                self.liked_posts,
                weights=range(1, len(self.liked_posts) + 1),
                k=1
            )[0]

        try:
            await update_msg("🔄 Ranking posts")

            ref_tags = set(like_this["tags"])
            viewed_post_ids_set = set(self.viewed_post_ids)
            ref_embedding = CLIP.get_post_tensor(like_this).squeeze(0)

            await update_msg("🔄 Similarity calculation")

            load_points = 0
            iteration_time: float = 0
            for post in posts:
                start_time = time.time()
                if iteration_time > 1.5:
                    iteration_time = 0
                    load_points += 1
                    await update_msg("🔄 Ranking posts", load_points)
                    if load_points == 3:
                        load_points = 0

                likeness = 0

                if int(post["id"]) in viewed_post_ids_set:
                    post["likeness"] = likeness
                    continue

                for tag in post["tags"]:
                    if tag in ref_tags:
                        likeness += 1
                    else:
                        likeness -= 0.1
                post["likeness"] = likeness
                end_time = time.time()
                iteration_time += end_time - start_time

            top_posts = heapq.nlargest(
                POST_LIKE_THIS_CLIP_CNT,
                posts,
                key=lambda p: p["likeness"]
            )

            await update_msg("🔄 Load embeddings")

            embeddings = torch.stack([
                CLIP.get_post_tensor(post).squeeze(0)
                for post in top_posts
            ])
            sims_like = embeddings @ ref_embedding

            disliked_embeddings = torch.stack([
                post["embedding"]
                for post in self.disliked_posts
            ])
            sims_dislike = (embeddings @ disliked_embeddings.T).max(dim=1).values

            await update_msg("🔄 Finding best post")
            for i, post in enumerate(top_posts):

                tag_score = post["likeness"]
                sims_like_score = sims_like[i].item()
                sims_dislike_score = sims_dislike[i].item()

                post["likeness"] = (
                    tag_score * 0.6 +
                    sims_like_score * 8 -
                    sims_dislike_score * 8
                )

            top_20 = heapq.nlargest(
                20,
                top_posts,
                key=lambda p: p["likeness"]
            )
            top_20.sort(key=lambda p: p["likeness"], reverse=True)

            weights = [
                100,70,50,35,25,
                18,14,11,9,8,
                7,6,5,4,3,
                2,2,1,1,1
            ]

            return random.choices(
                top_20,
                weights=weights,
                k=1
            )[0]
        
        except Exception as e:
            import traceback
            traceback.print_exc()

        return None

USERS = {}

def get_user(user_id):
    if user_id not in USERS:
        USERS[user_id] = User(user_id, R34_CLIENT)

    return USERS[user_id]