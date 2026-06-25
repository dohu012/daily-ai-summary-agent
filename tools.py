"""
LLM 可调用的工具集。

提供给模型的 4 个工具：
1. filter_email    — 标记为无关，跳过
2. summarize_email — 生成邮件摘要
3. archive_email   — 存档到 Google Drive
4. create_reminder — 创建待办提醒
"""

from typing import Any

from gdrive import GoogleDriveClient
from tracer import Tracer

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "filter_email",
            "description": "标记该邮件为无关/垃圾，直接跳过，不做任何处理。适用场景：广告、营销推送、社交媒体通知、已回复过的感谢信等无需关注的内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["spam", "promotion", "notification", "newsletter", "other_irrelevant"],
                        "description": "过滤的类型标签",
                    }
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_email",
            "description": "生成邮件的中文摘要。适用场景：需要了解内容但无需存档或行动的邮件，如资讯、报告、一般通知。",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "邮件的中文摘要，2-5 句话概括核心内容",
                    },
                    "importance": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "重要程度",
                    },
                },
                "required": ["summary", "importance"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "archive_email",
            "description": "将邮件摘要及关键内容存档到 Google Drive。适用场景：重要文档、合同、收据、需要长期保留的邮件。调用后会自动上传。",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "邮件的中文摘要，2-5 句话概括核心内容",
                    },
                    "importance": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "重要程度",
                    },
                    "archive_reason": {
                        "type": "string",
                        "description": "为什么需要存档这封邮件（如：合同备份、消费凭证、重要通知等）",
                    },
                },
                "required": ["summary", "importance", "archive_reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "创建待办提醒。适用场景：需要回复、需要后续行动的邮件（如会议邀请、任务指派、账单支付提醒等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "邮件的中文摘要",
                    },
                    "action_needed": {
                        "type": "string",
                        "description": "需要执行的具体行动（如：在周五前回复、支付账单、准备会议材料）",
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["today", "this_week", "this_month", "no_rush"],
                        "description": "紧急程度",
                    },
                },
                "required": ["summary", "action_needed", "urgency"],
            },
        },
    },
]


def execute_tool(
    name: str,
    args: dict[str, Any],
    mail_subject: str,
    mail_sender: str,
    mail_body: str,
    mail_date: str,
    tracer: Tracer,
    gdrive: GoogleDriveClient | None = None,
) -> str:
    """执行工具调用并返回结果描述。"""
    if name == "filter_email":
        return f"已过滤：{args.get('category', 'unknown')}"

    elif name == "summarize_email":
        summary = args.get("summary", "")
        importance = args.get("importance", "low")
        return f"已摘要 (重要性: {importance})：{summary}"

    elif name == "archive_email":
        if gdrive is None:
            raise RuntimeError("Google Drive client 未初始化")
        summary = args.get("summary", "")
        importance = args.get("importance", "low")
        reason = args.get("archive_reason", "")

        full_content = f"## 摘要\n{summary}\n\n## 存档原因\n{reason}\n\n---\n\n{mail_body}"
        link = gdrive.archive_email(mail_subject, mail_sender, mail_date, full_content)
        return f"已存档至 Google Drive (重要性: {importance})：{summary}\n链接：{link}"

    elif name == "create_reminder":
        summary = args.get("summary", "")
        action = args.get("action_needed", "")
        urgency = args.get("urgency", "no_rush")
        return f"已创建提醒 (紧急程度: {urgency})：{action}\n摘要：{summary}"

    else:
        raise ValueError(f"未知工具: {name}")
