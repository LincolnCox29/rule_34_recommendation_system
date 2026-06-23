import datetime
import sqlite3
from clip import CLIP
import torch

ZERO_TENSOR_BLOB = CLIP.tensor_to_blob(
    torch.zeros(512)
)

class Data_base:

    def __init__(self):
        self.__db = sqlite3.connect("users.db")
        self.__cursor = self.__db.cursor()
        self.__create_tags_table()
        self.__create_users_table()

    def commit(self):
        self.__db.commit()

    def close(self):
        self.__db.close()

    def create_tag(self, tag_name, user_id):
        self.__cursor.execute(
            """
            INSERT OR IGNORE INTO tags (name, user_id)
            VALUES (?, ?)
            """,
            (tag_name, user_id)
        )

    def create_user(self, id):
        self.__cursor.execute(
            """
            INSERT OR IGNORE INTO users 
            (id, like_tensor, dislike_tensor)
            VALUES (?,?,?)
            """,
            (id, ZERO_TENSOR_BLOB, ZERO_TENSOR_BLOB)
        )
        self.__db.commit()

    def __create_users_table(self):
        self.__cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                reaction_count INTEGER DEFAULT 0,
                ai_filter BOOL DEFAULT FALSE,
                today_posts_counter INTEGER DEFAULT 0,
                today_posts_counter_reload_time REAL DEFAULT 0.0,
                subscription_end REAL DEFAULT 0.0,
                like_tensor BLOB,
                dislike_tensor BLOB 
            )
            """
        )
        self.__db.commit()

    def get_today_posts_counter_reload_time(self, id):
        row = self.__cursor.execute(
            "SELECT today_posts_counter_reload_time FROM users WHERE id=?",
            (id,)
        ).fetchone()

        if row is None:
            return 0.0
    
        return row[0]
    
    def get_today_posts_counter(self, id):
        row = self.__cursor.execute(
            "SELECT today_posts_counter FROM users WHERE id=?",
            (id,)
        ).fetchone()
    
        if row is None:
            return 0.0

        return row[0]

    def update_today_posts_counter_reload_time(self, id):
        self.__cursor.execute(
            f"""
            UPDATE users
            SET today_posts_counter_reload_time = today_posts_counter_reload_time + 86400
            WHERE id=?
            """,
            (id,)
        )

    def update_today_posts_counter(self, id):
        self.__cursor.execute(
            f"""
            UPDATE users
            SET today_posts_counter = today_posts_counter + 1
            WHERE id=?
            """,
            (id,)
        )

    def set_today_posts_counter(self, user_id, value):
        self.__cursor.execute(
            """
            UPDATE users
            SET today_posts_counter=?
            WHERE id=?
            """,
            (value, user_id)
        )

    def set_today_posts_counter_reload_time(self, user_id, value):
        self.__cursor.execute(
            """
            UPDATE users
            SET today_posts_counter_reload_time=?
            WHERE id=?
            """,
            (value, user_id)
        )

    def __create_tags_table(self):
        self.__cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tags (
                name TEXT,
                user_id INTEGER,
                dislikes INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                skips INTEGER DEFAULT 0,
                PRIMARY KEY (name, user_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        self.__db.commit()

    def user_exists(self, id):
        return self.__cursor.execute(
            "SELECT 1 FROM users WHERE id=?",
            (id,)
        ).fetchone() is not None
    
    def tag_exists(self, name, user_id):
        return self.__cursor.execute(
            "SELECT 1 FROM tags WHERE name=? AND user_id=?",
            (name,user_id)
        ).fetchone() is not None
    
    def get_tag_stats(self, name, user_id):
        return self.__cursor.execute(
            """
            SELECT likes, dislikes, skips
            FROM tags
            WHERE name=? AND user_id=?
            """,
            (name, user_id)
        ).fetchone()
    
    def get_user_tags(self, user_id):
        rows = self.__cursor.execute(
            "SELECT name FROM tags WHERE user_id=?",
            (user_id,)
        ).fetchall()

        return {row[0] for row in rows}
    
    def reaction_on_tag(self, name, user_id, reaction):
        self.__cursor.execute(
            f"""
            UPDATE tags
            SET {reaction} = {reaction} + 1
            WHERE name=? AND user_id=?
            """,
            (name, user_id)
        )

    def inc_reaction_counter(self, id):
        self.__cursor.execute(
            f"""
            UPDATE users
            SET reaction_count = reaction_count + 1
            WHERE id=?
            """,
            (id,)
        )

    def get_user_ai_filter(self, id):
        row = self.__cursor.execute(
            """
            SELECT ai_filter
            FROM users
            WHERE id=?
            """,
            (id,)
        ).fetchone()
    
        return row[0]

    def turn_user_ai_filter(self, id):
        self.__cursor.execute(
            f"""
            UPDATE users
            SET ai_filter = NOT ai_filter
            WHERE id=?
            """,
            (id,)
        )

    def get_user_tensor(self, id, type):
        row = self.__cursor.execute(
            f"""
            SELECT {type}_tensor
            FROM users
            WHERE id=?
            """,
            (id,)
        ).fetchone()

        if row is None:
            return None
        
        blob = row[0]

        tensor = CLIP.tensor_from_blob(blob)
        return tensor

    def update_user_tensor(self, id, new_value, type):
        blob = CLIP.tensor_to_blob(new_value)
        return self.__cursor.execute(
            f"""
            UPDATE users 
            SET {type}_tensor = ?
            WHERE id=?
            """,
            (blob, id)
        )
    
    def get_sub_end(self, user_id):
        row = self.__cursor.execute(
            f"""
            SELECT subscription_end 
            FROM users
            WHERE id=?
            """,
            (user_id,)
        ).fetchone()

        if row is None:
            return 0.0

        return row[0]
    
    def update_sub_end(self, user_id, subscription_end):
        return self.__cursor.execute(
            f"""
            UPDATE users
            SET subscription_end = ?
            WHERE id=?
            """,
            (subscription_end, user_id)
        )
    
    def dump_user_to_file(self, user_id, filename=None):

        if filename is None:
            filename = f"user_dump_{user_id}.txt"

        with open(filename, "w", encoding="utf-8") as f:

            f.write(f"=== USER {user_id} ===\n")

            f.write(f"AI Filter: {DB.get_user_ai_filter(user_id)}\n")
            f.write(f"Subscription End: {DB.get_sub_end(user_id)}\n\n")

            f.write("=== TAGS ===\n")

            tags = sorted(DB.get_user_tags(user_id))

            for tag in tags:

                likes, dislikes, skips = DB.get_tag_stats(
                    tag,
                    user_id
                )

                f.write(
                    f"{tag:<40}"
                    f"L:{likes:<5}"
                    f"D:{dislikes:<5}"
                    f"S:{skips:<5}\n"
                )

            f.write("\n=== LIKE TENSOR ===\n")

            like_tensor = DB.get_user_tensor(
                user_id,
                "like"
            )

            if like_tensor is not None:
                f.write(
                    f"Shape: {tuple(like_tensor.shape)}\n"
                )
                f.write(
                    f"Norm: {torch.norm(like_tensor).item()}\n"
                )
                f.write(
                    f"Values:\n{like_tensor.tolist()}\n"
                )

            f.write("\n=== DISLIKE TENSOR ===\n")

            dislike_tensor = DB.get_user_tensor(
                user_id,
                "dislike"
            )

            if dislike_tensor is not None:
                f.write(
                    f"Shape: {tuple(dislike_tensor.shape)}\n"
                )
                f.write(
                    f"Norm: {torch.norm(dislike_tensor).item()}\n"
                )
                f.write(
                    f"Values:\n{dislike_tensor.tolist()}\n"
                )

        print(f"Dump saved to {filename}")

DB: Data_base = Data_base()