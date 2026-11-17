from functools import lru_cache
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DropSafe Core Application Settings.

    Configured via environment variables or .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application metadata
    APP_NAME: str = "DropSafe Backend"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SECRET_KEY: str = "insecure-change-this-in-production-super-secret-key-min-32-chars"

    # CORS Configuration
    ALLOWED_ORIGINS: Union[str, List[str]] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v  # type: ignore
        return []

    # Database Settings (PostgreSQL + Psycopg 3)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "dropsafe"
    POSTGRES_PASSWORD: str = "dropsafe_secret"
    POSTGRES_DB: str = "dropsafe_db"
    DATABASE_URL: Union[str, None] = None
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_ECHO: bool = False

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Union[str, None], info) -> str:
        if isinstance(v, str) and v.strip():
            return v
        data = info.data
        user = data.get("POSTGRES_USER", "dropsafe")
        password = data.get("POSTGRES_PASSWORD", "dropsafe_secret")
        server = data.get("POSTGRES_SERVER", "localhost")
        port = data.get("POSTGRES_PORT", 5432)
        db = data.get("POSTGRES_DB", "dropsafe_db")
        return f"postgresql+psycopg://{user}:{password}@{server}:{port}/{db}"

    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage Settings (Cloudflare R2 / S3 / MinIO)
    STORAGE_BACKEND: str = "r2"  # "r2", "s3", "minio", "memory"
    STORAGE_LOCAL_ROOT: str = "./data/storage"
    R2_ENDPOINT_URL: str = "http://localhost:9000"
    R2_ACCESS_KEY_ID: str = "minioadmin"
    R2_SECRET_ACCESS_KEY: str = "minioadmin"
    R2_BUCKET_NAME: str = "dropsafe-vault"
    R2_REGION: str = "auto"

    # Sharing & Link Delivery
    ENABLE_SHARE_LINKS: bool = True

    # Security & Cryptography
    ALGORITHM: str = "HS256"
    JWT_SIGNING_KEY: Union[str, None] = None
    JWT_ISSUER: str = "dropsafe-auth"
    JWT_AUDIENCE: str = "dropsafe-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Cookie Settings
    ACCESS_COOKIE_NAME: str = "dropsafe_access_token"
    REFRESH_COOKIE_NAME: str = "dropsafe_refresh_token"
    COOKIE_SAMESITE: str = "lax"
    COOKIE_SECURE: bool = False

    @field_validator("JWT_SIGNING_KEY", mode="before")
    @classmethod
    def assemble_jwt_signing_key(cls, v: Union[str, None], info) -> str:
        if isinstance(v, str) and v.strip():
            return v
        return info.data.get("SECRET_KEY", "insecure-change-this-in-production-super-secret-key-min-32-chars")

    # Attribute Authority & Credential Signing
    ATTRIBUTE_ISSUER_KEY_ID: str = "dropsafe-attribute-authority-v1"
    ATTRIBUTE_ISSUER_SIGNING_KEY: str = ""

    # Blockchain Audit Verification Settings
    BLOCKCHAIN_NETWORK: str = "sepolia"
    BLOCKCHAIN_RPC_URL: str = ""
    AUDIT_BATCH_INTERVAL_SECONDS: int = 300
    AUDIT_BATCH_SIZE: int = 100
    AUDIT_ANCHOR_MODE: str = "mock"  # "mock", "local", "sepolia"
    EVM_RPC_URL: str = ""
    ANCHOR_CONTRACT_ADDRESS: str = "0x0000000000000000000000000000000000000000"
    ANCHOR_SIGNER_PRIVATE_KEY: str = ""
    EVM_SIGNER_PRIVATE_KEY: str = ""

    # Logging Settings
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = False

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT.lower() in ("testing", "test")


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()


settings = get_settings()
