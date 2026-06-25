import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent


class Config:
    # DeepSeek
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # IMAP
    imap_server: str = os.getenv("IMAP_SERVER", "imap.gmail.com")
    imap_port: int = int(os.getenv("IMAP_PORT", "993"))
    email_account: str = os.getenv("EMAIL_ACCOUNT", "")
    email_password: str = os.getenv("EMAIL_PASSWORD", "")

    # Google Drive
    google_drive_folder_id: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    google_credentials_path: str = os.getenv(
        "GOOGLE_CREDENTIALS_PATH", str(BASE_DIR / "credentials.json")
    )
    google_token_path: str = os.getenv(
        "GOOGLE_TOKEN_PATH", str(BASE_DIR / "token.json")
    )

    # Trace & Output
    trace_dir: str = os.getenv("TRACE_DIR", str(BASE_DIR / "traces"))
    output_dir: str = os.getenv("OUTPUT_DIR", str(BASE_DIR / "output"))


config = Config()
