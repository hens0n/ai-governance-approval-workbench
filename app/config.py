from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/workbench.db"
    attachments_dir: Path = Path("./data/attachments")
    session_secret: str = "dev-only-change-me"
    ai_features_enabled: bool = False
    environment: str = "dev"

    def model_post_init(self, __context) -> None:
        if self.environment != "dev" and self.session_secret == "dev-only-change-me":
            raise RuntimeError(
                "SESSION_SECRET must be set to a non-default value when ENVIRONMENT != 'dev'"
            )


settings = Settings()
