import shutil
import subprocess
import sys


def warn(message):
    print(f"system_inspection_report: {message}", file=sys.stderr)


def sanitized(text, token):
    if token:
        return text.replace(token, "***")
    return text


def run_delivery(label, cmd, token, input_text=None):
    result = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = sanitized(result.stderr.strip(), token) or f"exit code {result.returncode}"
        warn(f"{label} failed: {detail}")
        return False
    return True


def deliver_report(config):
    delivery_failures = []

    if config.send_email != "0":
        if shutil.which("mail"):
            subject = f"[巡检] {config.host_name} {config.now}"
            ok = run_delivery(
                "email",
                ["mail", "-s", subject, config.recipient],
                config.telegram_bot_token,
                config.report_file.read_text(encoding="utf-8"),
            )
            if not ok:
                delivery_failures.append("email")
        else:
            warn("email enabled but mail command is not available")
            delivery_failures.append("email")

    if config.send_telegram != "0":
        if config.telegram_bot_token and config.telegram_chat_id:
            ok = run_delivery(
                "telegram summary",
                [
                    "curl", "-fsS", "-X", "POST",
                    f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage",
                    "-d", f"chat_id={config.telegram_chat_id}",
                    "--data-urlencode", f"text@{config.summary_file}",
                ],
                config.telegram_bot_token,
            )
            if not ok:
                delivery_failures.append("telegram summary")
            ok = run_delivery(
                "telegram document",
                [
                    "curl", "-fsS", "-X", "POST",
                    f"https://api.telegram.org/bot{config.telegram_bot_token}/sendDocument",
                    "-F", f"chat_id={config.telegram_chat_id}",
                    "-F", f"caption=完整环境巡检报告 {config.now}",
                    "-F", f"document=@{config.report_file};type=text/html",
                ],
                config.telegram_bot_token,
            )
            if not ok:
                delivery_failures.append("telegram document")
        else:
            warn("telegram enabled but TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing")

    return delivery_failures
