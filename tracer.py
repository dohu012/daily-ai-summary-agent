import json
import os
from datetime import datetime, timezone
from pathlib import Path

from config import config


class Tracer:
    def __init__(self):
        self._dir = Path(config.trace_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / f"trace_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
        self._buffer: list[dict] = []

    def log_decision(
        self,
        mail_uid: str,
        mail_subject: str,
        mail_sender: str,
        decision: str,
        reasoning: str,
        tool_name: str | None,
        tool_args: dict | None,
        result: str,
        error: str | None = None,
    ):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mail_uid": mail_uid,
            "mail_subject": mail_subject,
            "mail_sender": mail_sender,
            "decision": decision,
            "reasoning": reasoning,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "result": result,
            "error": error,
        }
        self._buffer.append(entry)
        self._flush()

    def log_error(self, context: str, error: str):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "context": context,
            "error": error,
        }
        self._buffer.append(entry)
        self._flush()

    def _flush(self):
        try:
            with open(self._file, "a", encoding="utf-8") as f:
                for entry in self._buffer:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._buffer.clear()
        except Exception:
            pass
