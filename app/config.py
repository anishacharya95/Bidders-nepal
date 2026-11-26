import os

class Settings:
    app_name = os.getenv("APP_NAME", "Bidders Nepal API")
    database_url = os.getenv("DATABASE_URL", "sqlite:///./bidders_nepal.db")
    jwt_secret = os.getenv("JWT_SECRET", "")
    jwt_exp_minutes = int(os.getenv("JWT_EXP_MINUTES", "720"))
    admin_email = os.getenv("ADMIN_EMAIL", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    cors_origins = os.getenv("CORS_ORIGINS", "*")

settings = Settings()
