import os


class Settings:
    app_name = "CheckFlow"
    api_prefix = "/api/v1"
    database_url = os.getenv("CHECKFLOW_DATABASE_URL", "sqlite:///./checkflow.db")
    jwt_secret = os.getenv("CHECKFLOW_JWT_SECRET", "checkflow-dev-secret-change-before-production")
    jwt_algorithm = "HS256"


settings = Settings()
