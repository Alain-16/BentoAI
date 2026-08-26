from enum import Enum
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEV_PLACEHOLDER_SECRET="dev-secret-change-me"

_BASE_CONFIG = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
)

class Environment(str, Enum):

    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class AppSettings(BaseSettings):

    model_config = _BASE_CONFIG | SettingsConfigDict(env_prefix="APP_")

    name: str = "BentoAI"
    environment : Environment = Environment.LOCAL
    debug: bool = True
    api_prefix: str = "/api/v1"

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


class DatabaseSettings(BaseSettings):
    model_config = _BASE_CONFIG | SettingsConfigDict(env_prefix="DB_")

    url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://bentoai:bentoai@localhost:5432/bentoai"
    ) 

    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10

    pool_pre_ping: bool = True

    @property
    def url_str(self) -> str:
        return str(self.url)


class JWTSettings(BaseSettings):
    model_config = _BASE_CONFIG | SettingsConfigDict(env_prefix="JWT_")

   
    secret_key: SecretStr = SecretStr(DEV_PLACEHOLDER_SECRET)

    algorithm: str = "HS256"

    
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30


class OTPSettings(BaseSettings):
    model_config = _BASE_CONFIG | SettingsConfigDict(env_prefix="OTP_")

    code_length: int = 6
    ttl_minutes: int = 10

   
    max_attempts: int = 5
    resend_cooldown_seconds: int = 60

    
    pepper: SecretStr = SecretStr(DEV_PLACEHOLDER_SECRET)


class EmailSettings(BaseSettings):
    model_config = _BASE_CONFIG | SettingsConfigDict(env_prefix="EMAIL_")

   
    backend: Literal["console", "smtp"] = "console"

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_use_tls: bool = True

    from_address: str = "no-reply@bentoai.local"
    from_name: str = "BentoAI"

    @model_validator(mode="after")
    def _require_host_for_smtp(self) -> "EmailSettings":
       
        if self.backend == "smtp" and not self.smtp_host:
            raise ValueError("EMAIL_SMTP_HOST is required when EMAIL_BACKEND=smtp")
        return self


class LLMSettings(BaseSettings):
    model_config = _BASE_CONFIG | SettingsConfigDict(env_prefix="LLM_")

    api_key: SecretStr = SecretStr("")

    
    model: str = "gpt-5.6-terra"
    max_tokens: int = 4096
    timeout_seconds: int = 60


class Settings(BaseSettings):
    """Root configuration object composing every group."""

    model_config = _BASE_CONFIG

    app: AppSettings = Field(default_factory=AppSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    otp: OTPSettings = Field(default_factory=OTPSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)

    @model_validator(mode="after")
    def _guard_production_config(self) -> "Settings":
        
        if self.app.environment is not Environment.PRODUCTION:
            return self

        problems: list[str] = []

        if self.jwt.secret_key.get_secret_value() == DEV_PLACEHOLDER_SECRET:
            problems.append("JWT_SECRET_KEY is still the development placeholder")
        elif len(self.jwt.secret_key.get_secret_value()) < 32:
            problems.append("JWT_SECRET_KEY must be at least 32 characters")

        if self.otp.pepper.get_secret_value() == DEV_PLACEHOLDER_SECRET:
            problems.append("OTP_PEPPER is still the development placeholder")

        if not self.llm.api_key.get_secret_value():
            problems.append("LLM_API_KEY is not set")

        if self.app.debug:
            problems.append("APP_DEBUG must be false in production")

        if self.email.backend == "console":
            problems.append("EMAIL_BACKEND=console cannot be used in production")

        # Collect every problem before raising. Fixing config one crash at a
        # is miserable; the operator should see the full list in one pass.
        if problems:
            raise ValueError("Invalid production configuration: " + "; ".join(problems))

        return self