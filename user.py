import json
import math
import os
import random
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
R34_API_KEY = os.getenv("R34_API_KEY")
R34_USER_ID = os.getenv("R34_USER_ID")

TAGS_POP = None
def load_tags_pop():
    global TAGS_POP
    print(os.path.abspath("tags_pop.json"))
    try:
        with open("tags_pop.json", "r", encoding="utf-8") as file:
            TAGS_POP = json.load(file)
    except Exception as e:
        print("tags JSON loading exception: ", e)
load_tags_pop()

class User:

    def __init__(self, id):
        self.id = id
        self.json_path = f"users\\{self.id}.json"
        path = Path(self.json_path)
        if path.is_file():
            self.__load_json()
        else:
            self.__create_json()

    def __create_json(self):
        self.reactions = {}
        self.posts_cache = {}
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
        
    def save_user_data(self):
        data = {
            "reactions": self.reactions,
            "posts_cache": self.posts_cache,
            "config": self.config
        }
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
        tags = post["tags"].split()

        self.print_tags_weight(max=-3)

        for tag in tags:
            if tag not in self.reactions:
                self.reactions[tag] = {
                    "dis": 0,
                    "like": 0,
                    "skip": 0
                }
            self.reactions[tag][type] += 1

        self.save_user_data()

    def dislike_post(self, post):
        self.__reaction("dis", post)

    def like_post(self, post):
        self.__reaction("like", post)

    def skip_post(self, post):
        self.__reaction("skip", post)

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

        tags = post["tags"].split()
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
    
    def __build_query(self):

        query = []

        best_tags = self.__get_best_tags()

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

        disliked = []

        for tag in self.reactions:

            weight = self.__tag_weight(tag)

            if weight < -10:
                disliked.append((tag, weight))

        disliked.sort(key=lambda x: x[1])

        query.extend(
            f"-{tag}"
            for tag, _ in disliked[:10]
        )

        if self.config["ai_filter"]:
            query.extend([
                "-ai_generated",
                "-stable_diffusion",
                "-midjourney",
                "-novelai",
                "-ia_generated"
            ])

        return " ".join(query)
    
    def next_post(self):

        for i in range(5):

            query = self.__build_query()
            print("QUERY:", query)

            pid = random.randint(0, 200)

            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "limit": 100,
                "pid": 0,
                "tags": query,
                "api_key": R34_API_KEY,
                "user_id": R34_USER_ID
            }

            headers = {
                "User-Agent": "Mozilla/5.0"
            }

            try:

                response = requests.get(
                    "https://api.rule34.xxx/index.php",
                    params=params,
                    headers=headers,
                    timeout=10
                )

                posts = response.json()
                
                print("STATUS:", response.status_code)
                print("TYPE:", type(posts))
                print("TEXT:", response.text[:500])

                if not isinstance(posts, list):
                    raise TypeError("Bad API response")

                if not posts:
                    continue

                best_post = None
                for post in posts:
                    if str(post["id"]) in self.posts_cache:
                        continue

                    score = self.__score_post(post)

                    post["user_score"] = score

                    if best_post == None or score > best_post["user_score"]:
                        best_post = post
                return best_post

            except Exception as e:
                print(e)
                continue

        return None
    
    def print_tags_weight(self, min = -999, max = 999):
        weights = {}

        for tag in self.reactions.keys():
            w = self.__tag_weight(tag)
            if w >= min or w <= max:
                weights[tag] = w

        sorted_by_val = dict(sorted(weights.items(), key=lambda x: x[1]))
        
        for tag in sorted_by_val.keys():
            print(f"Weight of the \"{tag}\": ", weights[tag])
        