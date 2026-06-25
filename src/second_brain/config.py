from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "second-brain"
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8088

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "secondbrain_dev"

    redis_url: str = "redis://localhost:6379/0"

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "second-brain"

    context_token_budget: int = 8192
    retrieval_top_k: int = 8
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    otel_enabled: bool = False
    otel_service_name: str = "second-brain"

    # Phase 4 — actuation & policy
    iot_dry_run: bool = True
    require_human_approval: bool = True
    iot_comfort_min_c: float = 18.0
    iot_comfort_max_c: float = 26.0
    iot_max_setpoint_delta: float = 5.0

    # Phase 6 — MQTT integration
    mqtt_enabled: bool = False
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_telemetry_topic: str = "secondbrain/telemetry/#"
    mqtt_command_topic_template: str = "secondbrain/commands/{device_id}"

    @property
    def llm_configured(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key != "sk-your-key-here")


@lru_cache
def get_settings() -> Settings:
    return Settings()
