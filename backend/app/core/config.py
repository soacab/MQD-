import os


DEFAULT_DEV_JWT_SECRET = "checkflow-dev-secret-change-before-production"


class Settings:
    app_name = "CheckFlow"
    api_prefix = "/api/v1"
    jwt_algorithm = "HS256"

    def __init__(self) -> None:
        self.validate_startup()

    @property
    def env(self) -> str:
        return os.getenv("CHECKFLOW_ENV", "development").strip().lower()

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def auth_mode(self) -> str:
        return os.getenv("CHECKFLOW_AUTH_MODE", "local").strip().lower()

    @property
    def database_url(self) -> str:
        return os.getenv("CHECKFLOW_DATABASE_URL", "sqlite:///./backend/checkflow.db")

    @property
    def jwt_secret(self) -> str:
        secret = os.getenv("CHECKFLOW_JWT_SECRET")
        if self.is_production and not secret:
            raise RuntimeError("CHECKFLOW_JWT_SECRET must be configured in production.")
        if self.is_production and secret == DEFAULT_DEV_JWT_SECRET:
            raise RuntimeError("CHECKFLOW_JWT_SECRET must not use the development default in production.")
        return secret or DEFAULT_DEV_JWT_SECRET

    @property
    def cors_origins(self) -> list[str]:
        raw = os.getenv("CHECKFLOW_CORS_ORIGINS", "*")
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def iam_authorize_url(self) -> str:
        return os.getenv("CHECKFLOW_IAM_AUTHORIZE_URL", "")

    @property
    def iam_token_url(self) -> str:
        return os.getenv("CHECKFLOW_IAM_TOKEN_URL", "")

    @property
    def iam_profile_url(self) -> str:
        return os.getenv("CHECKFLOW_IAM_PROFILE_URL", "")

    @property
    def iam_client_id(self) -> str:
        return os.getenv("CHECKFLOW_IAM_CLIENT_ID", "")

    @property
    def iam_client_secret(self) -> str:
        return os.getenv("CHECKFLOW_IAM_CLIENT_SECRET", "")

    @property
    def iam_redirect_uri(self) -> str:
        return os.getenv("CHECKFLOW_IAM_REDIRECT_URI", "")

    def validate_startup(self) -> None:
        _ = self.jwt_secret


settings = Settings()
