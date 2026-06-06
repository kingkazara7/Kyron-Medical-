import json, os, boto3
from functools import lru_cache

def load_secrets():
    client = boto3.client("secretsmanager", region_name="us-east-2")
    secret = client.get_secret_value(SecretId="scribe/prod")
    data = json.loads(secret["SecretString"])
    for k, v in data.items():
        os.environ.setdefault(k, v)
    return data

_secrets = None

def ensure_secrets():
    global _secrets
    if _secrets is None:
        _secrets = load_secrets()
    return _secrets

class Settings:
    def __init__(self):
        ensure_secrets()
        self.db_host = os.environ["DB_HOST"]
        self.db_port = int(os.environ.get("DB_PORT", 5432))
        self.db_name = os.environ["DB_NAME"]
        self.db_user = os.environ["DB_USER"]
        self.db_password = os.environ["DB_PASSWORD"]
        self.anthropic_api_key = os.environ["ANTHROPIC_API_KEY"]
        self.jwt_secret = os.environ["JWT_SECRET"]
        self.jwt_algorithm = "HS256"
        self.jwt_expire_minutes = 480

    @property
    def database_url(self):
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?sslmode=require"
        )

@lru_cache
def get_settings():
    return Settings()
