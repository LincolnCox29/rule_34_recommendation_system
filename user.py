import json
from pathlib import Path

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
        self.like_tags = {}
        self.posts_cache = {}
        self.config = {
            "ai_filter": False
        }
        self.save_user_data()

    def __load_json(self):
        with open(self.json_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        self.like_tags = data["like_tags"]
        self.posts_cache = data["posts_cache"]
        self.config = data["config"]
        
    def save_user_data(self):
        data = {
            "like_tags": self.like_tags,
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
        
