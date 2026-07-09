import json
from env import try_getenv
import os
import random
from pathlib import Path
import shutil
import torch
from subscription_manager import Subscription_manager
from posts_pool import POSTS_POOL
from rule_34_client import R34_CLIENT
from clip import CLIP
import heapq

AI_TAGS = [
    "ai_generated",
    "stable diffusion",
    "ai",
    "ai assisted"
]

NEXT_POST_SUB_POST_CNT = 10000
NEXT_POST_SUB_CLIP_CNT = 1000

NEXT_POST_POST_CNT = 5000
NEXT_POST_CLIP_CNT = 500

DISLIKE_WEIGHT = 8

LIKED_POSTS_MEM = 30
DISLIKED_POSTS_MEM = 15

#TAGS_POP = None
#def load_tags_pop():
#    global TAGS_POP
#    print("Tags pop json path: ", os.path.abspath("tags_pop.json"))
#    try:
#        with open("tags_pop.json", "r", encoding="utf-8") as file:
#            TAGS_POP = json.load(file)
#    except Exception as e:
#        print("tags JSON loading exception: ", e)
#        print("Trying to load tags pop")
#load_tags_pop()

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

        async def update_msg(text):
            nonlocal current_loading_text
            if (loading_msg is not None and current_loading_text != text):
                current_loading_text = text
                await loading_msg.edit_text(current_loading_text)

        await update_msg("🔄 Searching...")

        posts = POSTS_POOL.get_random_post(
            NEXT_POST_SUB_POST_CNT if self.sub_manager.is_premium() else NEXT_POST_POST_CNT,
            excluded_tags= AI_TAGS if self.config["ai_filter"] else None
        )

        if like_this == None:
            like_this = random.choices(
                self.liked_posts,
                weights=range(1, len(self.liked_posts) + 1),
                k=1
            )[0]

        try:
            await update_msg("🔄 Ranking posts...")

            ref_tags = set(like_this["tags"])
            viewed_post_ids_set = set(self.viewed_post_ids)
            ref_embedding = CLIP.get_post_tensor(like_this).squeeze(0)

            await update_msg("🔄 Similarity calculation...")

            for post in posts:

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

            top_posts = heapq.nlargest(
                NEXT_POST_SUB_CLIP_CNT if self.sub_manager.is_premium() else NEXT_POST_CLIP_CNT,
                posts,
                key=lambda p: p["likeness"]
            )

            await update_msg("🔄 Load embeddings...")

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

            await update_msg("🔄 Finding best post...")
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
            await update_msg("❌ Couldn't find post!")
            traceback.print_exc()

        return None

USERS = {}

def get_user(user_id):
    if user_id not in USERS:
        USERS[user_id] = User(user_id, R34_CLIENT)

    return USERS[user_id]