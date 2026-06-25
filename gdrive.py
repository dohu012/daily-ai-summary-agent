import io
import os
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from config import config

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveClient:
    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service

        creds = None
        token_path = config.google_token_path
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.google_credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def archive_email(self, subject: str, sender: str, date_str: str, content: str) -> str:
        """将邮件内容上传到 Google Drive，返回文件链接。"""
        service = self._get_service()

        safe_subject = "".join(c if c.isalnum() or c in " _-" else "_" for c in subject)[:80]
        file_name = f"{safe_subject}.md"

        body = f"# {subject}\n\n**From:** {sender}\n**Date:** {date_str}\n\n---\n\n{content}"

        media = MediaIoBaseUpload(
            io.BytesIO(body.encode("utf-8")),
            mimetype="text/markdown",
            resumable=True,
        )

        file_metadata = {"name": file_name}
        if config.google_drive_folder_id:
            file_metadata["parents"] = [config.google_drive_folder_id]

        uploaded = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id,webViewLink")
            .execute()
        )

        file_id = uploaded.get("id")
        return f"https://drive.google.com/file/d/{file_id}/view"
