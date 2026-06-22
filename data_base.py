import sqlite3

class Data_base:

    def __init__(self):
        self.__db = sqlite3.connect("users.db")
        self.__cursor = self.db.cursor()
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
        self.__db.commit()

    def create_user(self, id):
        self.__cursor.execute(
            """
            INSERT OR IGNORE INTO users (id)
            VALUES (?)
            """,
            (id,)
        )
        self.__db.commit()

    def __create_users_table(self):
        self.__cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                reaction_count INTEGER DEFAULT 0,
                ai_filter BOOL DEFAULT 0,
                subscription_end REAL DEFAULT 0.0,
                today_posts_counter_reload_time REAL DEFAULT 0.0,
                today_posts_counter INTEGER DEFAULT 0,
                like_tensor BLOB DEFAULT 0,
                dislike_tensor BLOB DEFAULT 0
            )
            """
        )
        self.__db.commit()

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
        return self.__cursor.execute(
            "SELECT * FROM tags WHERE user_id=?",
            (user_id,)
        ).fetchall()
    
    def reaction_on_tag(self, name, user_id, reaction):
        self.__cursor.execute(
            f"""
            UPDATE tags
            SET {reaction} = {reaction} + 1
            WHERE name=? AND user_id=?
            """,
            (name, user_id)
        )

    def get_user_tensor(self, id, type):
        return self.__cursor.execute(
            f"""
            SELECT {type}_tensor
            FROM users
            WHERE id=?
            """,
            (id,)
        ).fetchone()
    
    def update_user_tensor(self, id, new_value, type):
        return self.__cursor.execute(
            f"""
            UPDATE users 
            SET {type}_tensor = ?
            WHERE id=?
            """,
            (new_value, id)
        )

DB: Data_base = Data_base()