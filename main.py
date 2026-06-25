"""
Daily AI Summary Agent — 主入口

流程：
1. 从 IMAP 获取未读邮件
2. 逐封提交给 LLM Agent，模型自主决定处理策略
3. 执行工具调用（过滤/摘要/存档/提醒）
4. 生成每日摘要报告
5. 完整记录 trace 日志
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from config import config
from gdrive import GoogleDriveClient
from llm_agent import LLMAgent
from mail_fetcher import MailFetcher
from tracer import Tracer


def _setup_google_credentials():
    """在 CI 环境中从环境变量写入 credentials 和 token 文件。"""
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        with open(config.google_credentials_path, "w") as f:
            f.write(creds_json)

    token_json = os.getenv("GOOGLE_TOKEN_JSON")
    if token_json:
        with open(config.google_token_path, "w") as f:
            f.write(token_json)


def generate_report(results: list[dict], output_dir: Path) -> str:
    counts = {"filter": 0, "summarize": 0, "archive": 0, "remind": 0}
    for r in results:
        d = r.get("decision", "unknown")
        if d in counts:
            counts[d] += 1

    reminders = [r for r in results if r.get("decision") == "remind"]
    archives = [r for r in results if r.get("decision") == "archive"]

    lines = [
        "# 每日邮件摘要报告",
        f"生成时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## 统计",
        f"- 共处理：{len(results)} 封",
        f"- 过滤：{counts['filter']} 封",
        f"- 摘要：{counts['summarize']} 封",
        f"- 存档：{counts['archive']} 封",
        f"- 提醒：{counts['remind']} 封",
        "",
    ]

    if reminders:
        lines.append("## ⚠ 待办提醒")
        for r in reminders:
            lines.append(f"- **{r['mail_subject']}**")
            lines.append(f"  {r['execution_result']}")
        lines.append("")

    if archives:
        lines.append("## 📁 已存档")
        for r in archives:
            lines.append(f"- **{r['mail_subject']}**")
            lines.append(f"  {r['execution_result']}")
        lines.append("")

    report = "\n".join(lines)

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"report_{datetime.now(timezone.utc).strftime('%Y%m%d')}.md"
    report_path = output_dir / filename
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    return report


def main():
    _setup_google_credentials()

    tracer = Tracer()

    # 初始化 Google Drive（如果配置了 credentials 则启用）
    gdrive = None
    if os.path.exists(config.google_credentials_path) or os.getenv("GOOGLE_CREDENTIALS_JSON"):
        try:
            gdrive = GoogleDriveClient()
        except Exception as e:
            tracer.log_error("gdrive_init", str(e))
            print(f"[WARN] Google Drive 初始化失败，存档功能不可用：{e}")

    agent = LLMAgent(tracer=tracer, gdrive=gdrive)

    # 加载已处理 UID，避免重复
    seen_path = Path(config.output_dir) / "seen_uids.txt"
    seen_path.parent.mkdir(parents=True, exist_ok=True)
    if seen_path.exists():
        agent.load_seen_uids(str(seen_path))

    fetcher = MailFetcher(seen_uids=agent._seen_uids)

    print("正在获取未读邮件…")
    try:
        mails = fetcher.fetch_unread()
    except Exception as e:
        tracer.log_error("mail_fetch", str(e))
        print(f"[ERROR] 邮件获取失败：{e}")
        return

    print(f"获取到 {len(mails)} 封新邮件，开始处理…")

    all_results: list[dict] = []

    for i, mail in enumerate(mails, 1):
        print(f"  [{i}/{len(mails)}] {mail.subject[:60]}…")
        try:
            result = agent.process_mail(
                uid=mail.uid,
                subject=mail.subject,
                sender=mail.sender,
                date_str=mail.date.strftime("%Y-%m-%d %H:%M"),
                body=mail.body_text,
            )
            all_results.append({
                "decision": result.decision,
                "mail_subject": mail.subject,
                "mail_sender": mail.sender,
                "tool_name": result.tool_name,
                "tool_args": result.tool_args,
                "execution_result": result.execution_result,
                "reasoning": result.reasoning,
            })
            print(f"    → {result.decision}: {result.execution_result[:100]}")
        except Exception as e:
            tracer.log_error(f"process_mail:{mail.uid}", str(e))
            print(f"    → [ERROR] {e}")
            all_results.append({
                "decision": "error",
                "mail_subject": mail.subject,
                "mail_sender": mail.sender,
                "tool_name": None,
                "tool_args": None,
                "execution_result": str(e),
            })

    # 保存已处理 UID
    agent.save_seen_uids(str(seen_path))

    # 生成并输出报告
    output_dir = Path(config.output_dir)
    report = generate_report(all_results, output_dir)
    print("\n" + report)

    print(f"\nTrace 日志：{tracer._file}")
    print("处理完毕。")


if __name__ == "__main__":
    main()
