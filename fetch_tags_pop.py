import requests
from env import R34_API_KEY, R34_USER_ID
import json
import time
from dotenv import load_dotenv

load_dotenv()

def normalize_tag(tag):
    return (
        tag.strip()
        .lower()
        .rstrip(",")
    )

def tags_pop_to_json(tags: dict):

    for key in tags.keys():
        if tags[key] == 1:
            del tags[key]

    sorted_tags = dict(
        sorted(
            tags.items(),
            key=lambda x: x[1],
            reverse=True
        )
    )

    with open(
        "tags_pop.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            sorted_tags,
            file,
            ensure_ascii=False,
            indent=4
        )

def get_posts(pid):
   
    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": 1,
        "limit": 100,
        "pid": pid,
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
            timeout=20
        )

        print(response)
        posts = response.json()

        return posts
    except Exception as e:
        print("Error:", e)
        return None

def fetch_tags_pop():

    tags = {}
    pid = 0

    for pid in range(0, 500):
        print(f"get posts for pid: {pid}")
        posts = None
        for i in range(0,5):
            if posts == None:
                posts = get_posts(pid)
            else:
                break

        time.sleep(0.5)

        if posts == None:
            continue

        for post in posts:
            for tag in post["tags"].split():

                tag = normalize_tag(tag)
                if not tag:
                    continue

                tags[tag] = tags.get(tag, 0) + 1

    return tags

if __name__ == "__main__":
    tags = fetch_tags_pop()
    print(tags)
    tags_pop_to_json(tags)