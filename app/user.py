from time import time as timestamp
from random import randint
from typing import List

from app.types import Json
from app.database import Database


__all__ = ["User"]


class User:
    name: str
    token: str
    password: str
    _id: int
    sessions: List

    # region GET funcs
    def get_user(self, id: int) -> Json:
        pass

    # endregion
    # region POST funcs
    def sign_up(self, name: str, password: str) -> bool:
        self.token = self.generate_token
        self.id = self.generate_id
        session = {
            "version": "1.0",
            "system": "Linux",
            "architecture": "x86_64",
            "release": "18.04.5 LTS",
        }

        with Database() as db:
            db.add_user(self.id, name, password, self.token, {str(int(timestamp())): session})
        return True

    def sign_in(self, name: str, token_or_pass: str) -> bool:
        with Database() as db:
            db.update_sessions()
        if token_or_pass == self.token:
            return True
        elif token_or_pass == self.password:
            self.token = self.generate_token
            return True
        return False

    def sign_out(self) -> None:
        pass

    # endregion
    # region Other funcs
    def update_password(self, old_pass: str, new_pass: str) -> bool:
        if self.password == old_pass:
            self.password = new_pass
            with Database() as db:
                db.update_password(self.id, new_pass)
            return True
        return False

    @property
    def generate_token(self):
        return f"{randint(100_000_000, 999_999_999)}:{''.join([chr(randint(97, 122)) if randint(0, 1) else chr(randint(65, 90)) for _ in range(20)])}"

    @property
    def generate_id(self) -> int:
        with Database() as db:
            while True:
                id = randint(100_000_000, 999_999_999)
                if db.check_id(id):
                    return id
