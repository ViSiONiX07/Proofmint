from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

class Settings(BaseSettings):
    PROJECT_NAME: str = "Proofmint Verification API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # In-memory guideline PDF ingestion limits.
    GUIDELINE_MAX_FILE_BYTES: int = 10 * 1024 * 1024
    GUIDELINE_MAX_REQUEST_BYTES: int = 20 * 1024 * 1024
    GUIDELINE_MAX_MULTIPART_OVERHEAD_BYTES: int = 256 * 1024
    GUIDELINE_MAX_FILES: int = 5
    GUIDELINE_MAX_PAGES: int = 200

    # CSV imports are parsed fully in memory before one transactional DB write.
    CSV_IMPORT_MAX_FILE_BYTES: int = 5 * 1024 * 1024
    CSV_IMPORT_MAX_ROWS: int = 10_000
    CSV_IMPORT_MAX_MULTIPART_OVERHEAD_BYTES: int = 64 * 1024
    
    # PostgreSQL is optional at application startup. Persistence operations require
    # either DATABASE_URL or all four POSTGRES_* connection fields.
    DATABASE_URL: SecretStr | None = None
    POSTGRES_SERVER: str | None = None
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: SecretStr | None = None
    POSTGRES_DB: str | None = None
    POSTGRES_PORT: int = 5432
    
    # CORS Configuration
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        extra="ignore"
    )

    def get_database_url(self) -> URL | None:
        """Return a PostgreSQL SQLAlchemy URL, or None when persistence is unconfigured."""
        if self.DATABASE_URL and self.DATABASE_URL.get_secret_value().strip():
            try:
                url = make_url(self.DATABASE_URL.get_secret_value())
            except Exception:
                raise ValueError("DATABASE_URL is not a valid SQLAlchemy URL.") from None
            if url.drivername == "postgresql":
                url = url.set(drivername="postgresql+psycopg")
            if url.drivername != "postgresql+psycopg":
                raise ValueError("DATABASE_URL must use PostgreSQL with the Psycopg 3 driver.")
            return url

        if not all((self.POSTGRES_SERVER, self.POSTGRES_USER, self.POSTGRES_PASSWORD, self.POSTGRES_DB)):
            return None
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        )

settings = Settings()
