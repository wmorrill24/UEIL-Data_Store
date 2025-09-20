from pydantic_settings import BaseSettings, SettingsConfigDict


# Configuration settings for the application using Pydantic
class Settings(BaseSettings):
    # MinIO Settings
    MINIO_ENDPOINT: str = "minio-server:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_DEFAULT_BUCKET: str = "raw-data"
    MINIO_USE_HTTPS: bool = False

    # PostgreSQL Settings
    PG_HOST: str = "postgres-metadata-db"
    PG_DATABASE: str
    PG_USER: str
    PG_PASSWORD: str
    PG_PORT: int = 5432

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8")


# Create a single, reusable instance of the settings
settings = Settings()
