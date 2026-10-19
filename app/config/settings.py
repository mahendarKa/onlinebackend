from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = (
        # "mysql+pymysql://root:root@localhost:3306/online_exam_portal"
        "mysql+pymysql://25E6HpKvtk5YTpc.root:9Dguib4fvXzDH05S@gateway01.ap-southeast-1.prod.aws.tidbcloud.com:4000/online_exam_portal"
    )

    SECRET_KEY: str = "hansetechhansetechhansetechhansetech"
    # DATABASE_URL: str
    # SECRET_KEY: str
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200


settings = Settings()