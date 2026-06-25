"""
LLM Agent — 基于 DeepSeek function-calling 的自主邮件处理决策。

每封邮件提交给模型，模型自主选择 4 个工具之一：
  filter_email | summarize_email | archive_email | create_reminder

支持模型多轮决策：一封邮件可先摘要，再决定是否存档或提醒。
"""

import json
import os
from dataclasses import dataclass

from openai import OpenAI

from config import config
from tools import TOOL_DEFINITIONS, execute_tool
from tracer import Tracer
from gdrive import GoogleDriveClient


SYSTEM_PROMPT = """你是一个智能邮件处理助手。你每天会收到一批新邮件，你的任务是对每封邮件做出处理决策。

你可以使用以下 4 个工具：

1. **filter_email** — 无关邮件直接过滤（广告、营销、社交媒体通知等）
2. **summarize_email** — 提取重点，生成简短中文摘要（资讯、报告、通知等）
3. **archive_email** — 摘要并上传到 Google Drive 存档（合同、收据、重要文件等）
4. **create_reminder** — 创建待办提醒（需要回复、需要行动的邮件）

决策原则：
- 广告、营销推送、社交通知 → filter_email
- 有信息量但无需存档 → summarize_email
- 重要文档、凭证、合同 → archive_email 或 archive_email + create_reminder
- 需要回复或执行动作 → create_reminder
- 一封邮件只调用一个最合适的工具
- 摘要用中文，简洁有力，2-5 句话
- 不要编造信息，根据邮件内容如实判断"""


@dataclass
class DecisionResult:
    decision: str       # "filter" | "summarize" | "archive" | "remind"
    reasoning: str      # 模型给的理由
    tool_name: str | None
    tool_args: dict | None
    execution_result: str


class LLMAgent:
    def __init__(self, tracer: Tracer, gdrive: GoogleDriveClient | None = None):
        self._client = OpenAI(
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
        )
        self._model = config.deepseek_model
        self._tracer = tracer
        self._gdrive = gdrive
        self._seen_uids: set[str] = set()

    def process_mail(
        self,
        uid: str,
        subject: str,
        sender: str,
        date_str: str,
        body: str,
    ) -> DecisionResult:
        """单封邮件处理：提交给 LLM，获取工具调用并执行。"""
        user_msg = f"""--- 新邮件 ---
发件人：{sender}
日期：{date_str}
主题：{subject}

正文：
{body}

请决定如何处理这封邮件。"""

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0.3,
        )

        msg = response.choices[0].message

        if msg.tool_calls:
            tool_call = msg.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            reasoning = msg.content or "模型选择了工具调用"

            try:
                exec_result = execute_tool(
                    name=tool_name,
                    args=tool_args,
                    mail_subject=subject,
                    mail_sender=sender,
                    mail_body=body,
                    mail_date=date_str,
                    tracer=self._tracer,
                    gdrive=self._gdrive,
                )
                error = None
            except Exception as e:
                exec_result = f"执行失败：{e}"
                error = str(e)
                self._tracer.log_error(f"tool_execution:{tool_name}", str(e))

            decision = _tool_to_decision(tool_name)

            self._tracer.log_decision(
                mail_uid=uid,
                mail_subject=subject,
                mail_sender=sender,
                decision=decision,
                reasoning=reasoning,
                tool_name=tool_name,
                tool_args=tool_args,
                result=exec_result,
                error=error,
            )

            return DecisionResult(
                decision=decision,
                reasoning=reasoning,
                tool_name=tool_name,
                tool_args=tool_args,
                execution_result=exec_result,
            )
        else:
            # 模型没有选择任何工具，默认当摘要处理
            content = msg.content or "模型未给出处理决策"
            self._tracer.log_decision(
                mail_uid=uid,
                mail_subject=subject,
                mail_sender=sender,
                decision="summarize",
                reasoning=content,
                tool_name=None,
                tool_args=None,
                result="模型未调用工具，按默认摘要处理",
            )
            return DecisionResult(
                decision="summarize",
                reasoning=content,
                tool_name=None,
                tool_args=None,
                execution_result=content,
            )

    def add_seen_uid(self, uid: str):
        self._seen_uids.add(uid)

    def load_seen_uids(self, path: str):
        if os.path.exists(path):
            with open(path, "r") as f:
                for line in f:
                    uid = line.strip()
                    if uid:
                        self._seen_uids.add(uid)

    def save_seen_uids(self, path: str):
        with open(path, "w") as f:
            for uid in sorted(self._seen_uids):
                f.write(uid + "\n")


def _tool_to_decision(tool_name: str) -> str:
    mapping = {
        "filter_email": "filter",
        "summarize_email": "summarize",
        "archive_email": "archive",
        "create_reminder": "remind",
    }
    return mapping.get(tool_name, "unknown")
