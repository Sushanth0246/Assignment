"""Central configuration. Values can be overridden with environment variables."""
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./certificates.db")
    )
    storage_dir: Path = field(
        default_factory=lambda: Path(os.getenv("CERT_STORAGE_DIR", "./storage/certificates"))
    )
    max_recipients: int = field(
        default_factory=lambda: int(os.getenv("MAX_RECIPIENTS", "1000"))
    )


settings = Settings()
