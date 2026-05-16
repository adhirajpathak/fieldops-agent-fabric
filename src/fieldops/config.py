from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: Literal["vertex", "openai", "mock"] = "mock"
    google_cloud_project: str | None = None
    google_cloud_region: str = "us-central1"
    vertex_model: str = "gemini-2.0-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    chroma_persist_dir: str = "./data/chroma"
    knowledge_base_dir: str = "./data/knowledge_base"

    otel_service_name: str = "fieldops-agent-fabric"
    otel_export_gcp: bool = False

    api_host: str = "0.0.0.0"
    api_port: int = 8080

    # LLM-native cost assumptions (USD per 1M tokens) for ROI dashboards
    cost_per_1m_input_tokens: float = 0.15
    cost_per_1m_output_tokens: float = 0.60


@lru_cache
def get_settings() -> Settings:
    return Settings()
