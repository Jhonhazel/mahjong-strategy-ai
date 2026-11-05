"""Small typed environment boundary; existing ML defaults are never implicit."""
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
V3_SHA256 = 'ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720'
V3_METADATA_SHA256 = '84423c71f8826a367b59b868aad1360fdbcc2c9a5cef6ce9bb3219b2bbd4488e'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='MAHJONG_', env_file=ROOT / '.env',
                                     extra='ignore', hide_input_in_errors=True)
    database_url: SecretStr
    session_secret: SecretStr
    environment: Literal['local', 'test', 'production'] = 'local'
    model_checkpoint_path: Path = ROOT / 'artifacts/models/mahjong_discard_mlp_v3.pt'
    model_metadata_path: Path = ROOT / 'artifacts/models/mahjong_discard_mlp_v3.metadata.json'
    dataset_contract_path: Path = ROOT / 'datasets/expanded_strict_v2/data_contract.json'
    contact_members_path: Path = ROOT / 'config/contact_members.json'
    max_active_games: int = Field(default=128, ge=1, le=1024)
    game_ttl_seconds: float = Field(default=3600, gt=0, le=86400)
    session_ttl_seconds: int = Field(default=86400, ge=1, le=2592000)
    cookie_secure: bool = False
    workers: int = Field(default=1, ge=1, le=1)
    host: str = '127.0.0.1'
    port: int = Field(default=8000, ge=1024, le=65535)
    allowed_hosts: list[str] = ['127.0.0.1', 'localhost', 'testserver']
    max_body_bytes: int = Field(default=16384, ge=1024, le=65536)
    database_timeout_seconds: int = Field(default=5, ge=1, le=30)

    @field_validator('database_url')
    @classmethod
    def postgres_only(cls, value):
        try:
            url = make_url(value.get_secret_value())
            if url.drivername not in ('postgresql', 'postgresql+psycopg') or not url.database:
                raise ValueError
            return SecretStr(url.set(drivername='postgresql+psycopg').render_as_string(hide_password=False))
        except Exception:
            raise ValueError('A valid PostgreSQL database URL is required') from None

    @field_validator('session_secret')
    @classmethod
    def strong_signing_secret(cls, value):
        secret = value.get_secret_value()
        if len(secret) < 32 or 'replace' in secret.lower() or len(set(secret)) < 8:
            raise ValueError('Provide a random session signing secret of at least32 characters')
        return value

    @field_validator('model_checkpoint_path', 'model_metadata_path', 'dataset_contract_path', 'contact_members_path')
    @classmethod
    def repository_path(cls, value):
        return (ROOT / value).resolve() if not value.is_absolute() else value.resolve()

    @model_validator(mode='after')
    def secure_production(self):
        if self.environment == 'production' and not self.cookie_secure:
            raise ValueError('HTTPS Secure cookies are required in production mode')
        return self
