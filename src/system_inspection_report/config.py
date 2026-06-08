from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import socket
import sys


DEFAULT_LOG_PATHS = [
    ["System logs", "/var/log"],
    ["Docker container logs", "/var/lib/docker/containers"],
]
DEFAULT_TIMER_UNITS = [
    "system-inspection-report.timer",
    "sysstat-collect.timer",
    "sysstat-summary.timer",
    "vnstat.service",
]


@dataclass(frozen=True)
class ReportConfig:
    report_tz: str
    bj: ZoneInfo
    report_now: datetime
    host_name: str
    now: str
    today: str
    report_date: object
    report_dir: Path
    report_file: Path
    summary_file: Path
    security_alert_dir: Path
    recipient: str
    send_telegram: str
    send_email: str
    telegram_bot_token: str
    telegram_chat_id: str
    delivery_mode: str
    local_tz: object
    root_disk_path: str
    data_disk_path: str
    data_root: str
    network_interface: str
    log_paths: list
    timer_units: list


def read_json_config():
    path = os.environ.get("SYSTEM_INSPECTION_CONFIG", "").strip()
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def env_or_config(name, config, key, default=""):
    value = os.environ.get(name)
    if value is not None:
        return value
    return config.get(key, default)


def load_config(argv=None):
    args = sys.argv[1:] if argv is None else argv
    file_config = read_json_config()
    report_tz = env_or_config("REPORT_TZ", file_config, "report_tz", "Asia/Shanghai")
    bj = ZoneInfo(report_tz)
    report_now = datetime.now(bj)
    today = report_now.strftime("%Y-%m-%d")
    report_dir = Path(env_or_config("REPORT_DIR", file_config, "report_dir", "reports"))
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"inspection-{today}-{report_now.strftime('%H%M%S')}.html"

    log_paths = file_config.get("log_paths", DEFAULT_LOG_PATHS)
    timer_units = file_config.get("timer_units", DEFAULT_TIMER_UNITS)

    return ReportConfig(
        report_tz=report_tz,
        bj=bj,
        report_now=report_now,
        host_name=env_or_config("HOST_NAME", file_config, "host_name", socket.gethostname().split(".", 1)[0]),
        now=f"{report_now.strftime('%Y-%m-%d %H:%M:%S')} ({report_tz})",
        today=today,
        report_date=report_now.date(),
        report_dir=report_dir,
        report_file=report_file,
        summary_file=report_file.with_suffix(".summary.txt"),
        security_alert_dir=Path(env_or_config("SECURITY_ALERT_DIR", file_config, "security_alert_dir", "")),
        recipient=args[0] if args else env_or_config("RECIPIENT", file_config, "recipient", "root"),
        send_telegram=env_or_config("SEND_TELEGRAM", file_config, "send_telegram", "0"),
        send_email=env_or_config("SEND_EMAIL", file_config, "send_email", "0"),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
        delivery_mode=env_or_config("DELIVERY_MODE", file_config, "delivery_mode", "best-effort"),
        local_tz=datetime.now().astimezone().tzinfo or timezone.utc,
        root_disk_path=env_or_config("ROOT_DISK_PATH", file_config, "root_disk_path", "/"),
        data_disk_path=env_or_config("DATA_DISK_PATH", file_config, "data_disk_path", "/var/lib"),
        data_root=env_or_config("DATA_ROOT", file_config, "data_root", "/var/lib"),
        network_interface=env_or_config("REPORT_NET_IFACE", file_config, "network_interface", ""),
        log_paths=[tuple(item) for item in log_paths],
        timer_units=list(timer_units),
    )
