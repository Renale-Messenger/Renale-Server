from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    host: str = "localhost"
    port: int = 3306
    user: SecretStr = SecretStr("user")
    password: SecretStr = SecretStr("password")
    db: str = "database"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


config = Settings()
