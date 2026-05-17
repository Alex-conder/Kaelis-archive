"""
全局配置管理。
支持从环境变量和 .env 文件读取，避免硬编码敏感信息。
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Kaelis"
    DEBUG: bool = False

    # NebulaGraph 连接配置
    NEBULA_HOST: str = "127.0.0.1"
    NEBULA_PORT: int = 9669
    NEBULA_USER: str = "root"
    NEBULA_PASSWORD: str = "nebula"
    NEBULA_SPACE: str = "kaelis"

    # OneKE 模型路径
    ONEKE_MODEL_PATH: str = "./models/oneke"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
