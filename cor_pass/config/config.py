from pydantic_settings import BaseSettings
import glob
import json
import os


class Settings(BaseSettings):
    sqlalchemy_database_url: str = (
        "postgresql+psycopg2://user:password@localhost:5432/postgres"
    )
    postgres_user: str = "POSTGRES_USER"
    postgres_password: str = "POSTGRES_PASSWORD"
    postgres_host: str = "POSTGRES_HOST"
    postgres_port: int = 5432
    postgres_db: str = "POSTGRES_DB"
    algorithm: str = "ALGORITHM"
    secret_key: str = "SECRET_KEY"
    mail_username: str = "MAIL_USERNAME"
    mail_password: str = "MAIL_PASSWORD"
    mail_from: str = "Cor.Auth@EXAMPLE.COM"
    mail_port: int = 0
    mail_server: str = "MAIL_SERVER"
    pythonpath: str = "PYTHONPATH"
    encryption_key: str = "ENCRYPTION_KEY"
    app_env: str = "ENVIROMENT"
    debug: bool = "FALSE"
    reload: bool = "False"
    aes_key: str = "key"
    basic_account_records: int = "NUMBER_OF_RECORDS"
    corid_facility_key: int = "1"
    admin_accounts: list = json.loads(os.getenv("ETERNAL_ACCOUNTS", "[]"))
    redis_host: str = "REDIS_HOST"
    redis_port: int = 5432
    redis_db: int = 123
    corid_version: int = 0
    corid_version_bit: int = 1
    corid_days_since_bit: int = 16
    corid_facility_bit: int = 16
    corid_patient_bit: int = 16
    corid_charset: str = "0123456789ABCDEFGHJKLMNPRSTUVWXYZ"
    eternal_accounts: list = json.loads(os.getenv("ETERNAL_ACCOUNTS", "[]"))
    access_token_expiration: int = 1
    refresh_token_expiration: int = 1
    eternal_token_expiration: int = 1
    authorization_via_email: bool = "True"
    authorization_via_google: bool = "True"
    authorization_via_facebook: bool = "True"
    allowed_redirect_urls: list = json.loads(os.getenv("ALLOWED_REDIRECT_URLS", "[]"))
    lawyer_accounts: list = json.loads(os.getenv("LAWYER_ACCOUNTS", "[]"))
    allowed_hosts: list = json.loads(os.getenv("ALLOWED_HOSTS", "[]"))
    marketing_email: str = "MARKETING_EMAIL"
    smb_user: str = "SMB_USER"
    smb_pass: str = "SMB_PASS"
    smb_server_ip: str ="SMB_SERVER_IP"
    smb_share: str ="SMB_SHARE"
    remote_name: str ="REMOTE_NAME"
    scan_interval_seconds: int = 60
    base_path: str = "BASE_PATH"
    smb_enabled: bool = False

    class Config:

        env_files = glob.glob("./*.env")
        env_file = env_files[0] if env_files else ".env"
        env_file_encoding: str = "utf-8"


settings = Settings()
