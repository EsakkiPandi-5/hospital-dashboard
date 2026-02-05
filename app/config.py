from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/hospital_analytics"
    app_title: str = "Hospital Resource Utilization & Patient Outcomes API"
    app_version: str = "1.0.0"

    class Config:
        env_file = ".env"


settings = Settings()
