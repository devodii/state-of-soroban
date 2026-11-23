from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = "postgresql://soroban:soroban@localhost:5442/soroban"
    workflow_file: Path = ROOT / "workflow" / "workflow.yaml"
    mainnet_rpc_url: str = "https://mainnet.sorobanrpc.com"
    clone_dir: Path | None = None
    pgschema_image: str = "pgplex/pgschema:1.14.1"
    github_tokens: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias=AliasChoices("GITHUB_TOKENS", "GITHUB_TOKEN"),
    )

    @field_validator("github_tokens", mode="before")
    @classmethod
    def split_tokens(cls, value: object) -> object:
        if isinstance(value, str):
            return [token.strip() for token in value.split(",") if token.strip()]
        return value

    @field_validator("clone_dir", mode="before")
    @classmethod
    def blank_is_unset(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
