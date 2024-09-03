import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from json import dumps, loads

from app.applib import Json, JsonD, random_id


__all__: List[str] = ["app_database", "Database", "Session"]


class Session:
    def __init__(self, version, system, architecture, release):
        self.version = version
        self.system = system
        self.architecture = architecture
        self.release = release

    def __str__(self) -> str:
        version = self.version
        system = self.system
        architecture = self.architecture
        release = self.release

        return f"""
Session info:
{version = !r}
{system = !r}
{architecture = !r}
{release = !r}
""".strip()


class Database:
    def __init__(self) -> None:
        self.sqlite_db_path: str = './server.sqlite'
        try:
            self.connection = sqlite3.connect(self.sqlite_db_path)
            self.connection.row_factory = sqlite3.Row
        except sqlite3.OperationalError as e:
            raise Exception(f"Error connecting to database: {e}")

        print("Database connection established successfully.")

    def __del__(self) -> None:
        if self.connection:
            self.connection.close()
            print("Database connection closed.")

    # region GET USER
    def get_users(self, limit: int = 50) -> Json:
        limit = int(limit)
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT id, name, sessions FROM users ORDER BY id DESC LIMIT %s", (limit,))
            rows = sql.fetchall()
        except Exception:
            return
        finally:
            sql.close()

        return [{"id": row["id"],
                 "name": row["name"],
                 "sessions": loads(row["sessions"])}
                for row in rows
                ]

    def get_user_by_id(self, id: int) -> JsonD:
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT id, name, sessions FROM users WHERE id = %s", (id,))
            row = sql.fetchone()
        except Exception:
            return
        finally:
            sql.close()

        return {"id": row["id"],
                "name": row["name"],
                "sessions": row["sessions"]}

    def get_user_by_name(self, name: str) -> JsonD:
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT id, name, sessions FROM users WHERE name = %s", (name,))
            row = sql.fetchone()
        except Exception:
            return
        finally:
            sql.close()

        return {"id": row["id"],
                "name": row["name"],
                "sessions": loads(row["sessions"])}

    def get_id_by_name(self, name: str) -> int:
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT id FROM users WHERE name = %s", (name,))
            row = sql.fetchone()
            return row["id"]
        finally:
            sql.close()

    def check_id(self, id: int) -> bool:
        """Returns True if user with given id does exist in the database."""
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT * FROM users WHERE id = %s", (id,))
            return sql.fetchone() is not None
        finally:
            sql.close()

    def check_name(self, name: str) -> bool:
        """Returns True if user with given name does exist in the database."""
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT * FROM users WHERE name = %s", (name,))
            return sql.fetchone() is not None
        finally:
            sql.close()

    @property
    def count_users(self) -> int:
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT COUNT(*) FROM users")
            return int(sql.fetchone()[0])
        finally:
            sql.close()

    # endregion
    # region POST USER
    def create_user(self, id: int, name: str, password: str, token: str, session: Json) -> Tuple[int, str]:
        """Register user in database and return user's id and token."""
        try:
            sql = self.connection.cursor()
            sql.execute(
                "INSERT INTO users (id, name, password, token, sessions, chats) VALUES (%s, %s, %s, %s, %s, %s)",
                (id, name, password, token, dumps([session]), "[]"),
            )
            self.connection.commit()
        except Exception:
            return (-1, "Error creating user")
        finally:
            sql.close()
        return (id, token)

    def login_user(self, name: str, password: str) -> Tuple[int, str]:
        """Authenticate user by name and password and return user's id and token. If credentials are invalid, return id -1(invalid) and an error message."""
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT id, name, password, token, sessions FROM users WHERE name = %s", (name,))
            user = sql.fetchone()
        except Exception:
            return
        finally:
            sql.close()

        if user and user["password"] == password:
            return (user["id"], user["token"])
        else:
            return (-1, "Invalid credentials")

    def update_sessions(self, id: int, token: str, new_session: Json) -> None:
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT token FROM users WHERE id = %s", (id,))
            user_token = sql.fetchone()["token"]
            if user_token == token:
                sql.execute(
                    "SELECT id, name, sessions FROM users WHERE id = %s", (id,)
                )
                sessions: List[Json] = sql.fetchall()
                sessions.append(new_session)
                sql.execute("UPDATE users SET sessions = %s WHERE id = %s", (sessions, id))
                self.connection.commit()
        finally:
            sql.close()

    def change_password(self, id: int, new_password: str) -> None:
        try:
            sql = self.connection.cursor()
            sql.execute("UPDATE users SET password = %s WHERE id = %s", (new_password, id))
            self.connection.commit()
        finally:
            sql.close()

    # endregion
    # region GET MESSAGE
    def get_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        limit = int(limit)
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT * FROM messages ORDER BY time DESC LIMIT %s", (limit,))
            rows = sql.fetchall()
        except Exception:
            return
        finally:
            sql.close()

        return [{"id": row["id"],
                 "chat": row["chat"],
                 "user": row["user"],
                 "text": row["text"],
                 "time": row["time"],
                 } for row in rows]

    @property
    def count_messages(self) -> int:
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT COUNT(*) FROM messages")
            return int(sql.fetchone()[0])
        finally:
            sql.close()

    # endregion
    # region POST MESSAGE
    def send_message(self, user_id: int, user_token: str, chat_id: int, text: str) -> bool:
        """Send a message to a chat."""
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT token FROM users WHERE id = %s", (user_id,))
            user_token_ = sql.fetchone()["token"]
            if user_token == user_token_:
                sql.execute("INSERT INTO messages (user, chat, text, time) VALUES (%s, %s, %s, CURRENT_TIMESTAMP)",
                            (user_id, chat_id, text))
                self.connection.commit()
            else:
                return False
        except Exception:
            return False
        finally:
            sql.close()

        return True

    # endregion
    # region GET CHATS
    def get_chats(self, limit: Optional[int] = 50) -> Json:
        try:
            sql = self.connection.cursor()
            if isinstance(limit, int):
                sql.execute("SELECT is_group, chat_id, title, members FROM chats ORDER BY chat_id DESC LIMIT %s", (limit,))
            else:
                sql.execute("SELECT is_group, chat_id, title, members FROM chats ORDER BY chat_id DESC")
            rows = sql.fetchall()
        except Exception:
            return
        finally:
            sql.close()

        return {"chats": [{"is_group": not not row["is_group"],
                           "id": row["chat_id"],
                           "title": row["title"],
                           "members": [{"id": i["id"], "name": i["name"], "sessions": loads(i["sessions"])}
                                       for i in loads(row["members"])]}
                          for row in rows]}

    def check_chat_title(self, title: str) -> bool:
        """Returns True if chat with given title already exists in the database."""
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT * FROM chats WHERE title = %s", (title,))
            return sql.fetchone() is not None
        finally:
            sql.close()

    def check_chat(self, chat_id: int) -> bool:
        """Returns True if chat with given id already exists in the database."""
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT * FROM chats WHERE chat_id = %s", (chat_id,))
            return sql.fetchone() is not None
        finally:
            sql.close()

    def get_chat_by_id(self, chat_id: int) -> Dict[str, Any]:
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT is_group, chat_id, title, description, members, admins FROM chats WHERE chat_id = %s", (chat_id,))
            row = sql.fetchone()
        except Exception:
            return
        finally:
            sql.close()

        return {
            "id": row["chat_id"],
            "title": row["title"],
            "description": row["description"],
            "is_group": row["is_group"],
            "members": loads(row["members"]),
            "admins": loads(row["admins"]),
        }

    @property
    def count_chats(self) -> int:
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT COUNT(*) FROM chats")
            return int(sql.fetchone()[0])
        finally:
            sql.close()

    # endregion
    # region POST CHATS
    def create_chat(self, creator_id: int, creator_token: str, is_group: bool, title: str, description: str, member_ids: List[int]) -> None:
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT token FROM users WHERE id = %s", (creator_id,))
            user_token = sql.fetchone()["token"]
            if user_token != creator_token:
                return
        except Exception:
            return
        finally:
            sql.close()

        creator = self.get_user_by_id(creator_id)
        admins: List[JsonD] = []
        members: List[JsonD] = []
        chat_id: int = -1

        if is_group:
            for i in member_ids:
                members.append(self.get_user_by_id(i))

            admins.append(creator)
            while True:
                chat_id = -random_id()
                if not self.check_chat(chat_id) and chat_id != -1:
                    break
        else:
            title = ""
            description = ""
        try:
            sql = self.connection.cursor()
            sql.execute("INSERT INTO chats (is_group, chat_id, title, description, members, admins) VALUES (%s, %s, %s, %s, %s, %s)",
                        (is_group, chat_id, title, description, dumps(members), dumps(admins)))
            self.connection.commit()
        finally:
            sql.close()

    def add_members(self, user_id: int, user_token: str, member_ids: List[int], chat_id: int) -> None:
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT token FROM users WHERE id = %s", (user_id,))
            user_token_ = sql.fetchone()["token"]
            if user_token != user_token_:
                return
        except Exception:
            return
        finally:
            sql.close()

        members: List = []

        for member in member_ids:
            members.append(self.get_user_by_id(member))
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT members FROM chats WHERE chat_id = ?", (chat_id,))
            current_members = loads(sql.fetchone()["members"])
            updated_members = current_members + members
            sql.execute("UPDATE chats SET members = ? WHERE chat_id = ?", (dumps(updated_members), chat_id))
            self.connection.commit()
        finally:
            sql.close()

    # endregion
    # region DELETE
    def delete_user(self, user_id: int, token: str) -> bool:
        try:
            sql = self.connection.cursor()
            sql.execute("SELECT token FROM users WHERE id = %s", (user_id,))
            user_token = sql.fetchone()["token"]
        except Exception:
            return False
        finally:
            sql.close()

        if user_token == token:
            try:
                sql = self.connection.cursor()
                sql.execute("DELETE FROM users WHERE id = %s", (user_id,))
                self.connection.commit()
                return True
            except Exception:
                return False
        else:
            return False
    # endregion


try:
    app_database: Database = Database()
except sqlite3.OperationalError:
    print("Error connecting to database.")
    print("Reconnect...")
    app_database: Database = Database()
