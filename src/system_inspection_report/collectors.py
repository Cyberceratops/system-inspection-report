import json
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .assess import status_by_percent


BJ = ZoneInfo("Asia/Shanghai")
REPORT_DATE = datetime.now(BJ).date()
LOCAL_TZ = datetime.now().astimezone().tzinfo
SECURITY_ALERT_DIR = Path()
CONFIG = None


def run(cmd, timeout=30):
    try:
        return subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout).stdout.strip()
    except Exception:
        return ""


def parse_size_to_bytes(text):
    text = str(text).strip()
    m = re.match(r"([0-9.]+)\s*([KMGT]?i?B|[kMGT]?B)?", text)
    if not m:
        return 0.0
    value = float(m.group(1))
    unit = (m.group(2) or "B").lower()
    scale = {
        "b": 1,
        "kb": 1000, "kib": 1024,
        "mb": 1000**2, "mib": 1024**2,
        "gb": 1000**3, "gib": 1024**3,
        "tb": 1000**4, "tib": 1024**4,
    }.get(unit, 1)
    return value * scale


def disk_usage(path):
    try:
        total, used, free = shutil.disk_usage(path)
        pct = used / total * 100 if total else 0
        return {"path": path, "total": total, "used": used, "free": free, "pct": pct, "status": status_by_percent(pct, 75, 90)}
    except Exception:
        return {"path": path, "total": 0, "used": 0, "free": 0, "pct": 0, "status": "WARN"}


def mem_info():
    data = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        k, rest = line.split(':', 1)
        data[k] = int(rest.strip().split()[0]) * 1024
    total = data.get('MemTotal', 0)
    avail = data.get('MemAvailable', 0)
    used = max(0, total - avail)
    swap_total = data.get('SwapTotal', 0)
    swap_free = data.get('SwapFree', 0)
    swap_used = max(0, swap_total - swap_free)
    mem_pct = used / total * 100 if total else 0
    swap_pct = swap_used / swap_total * 100 if swap_total else 0
    return {
        "total": total, "used": used, "avail": avail, "pct": mem_pct,
        "swap_total": swap_total, "swap_used": swap_used, "swap_free": swap_free, "swap_pct": swap_pct,
        "mem_status": status_by_percent(mem_pct, 75, 90),
        "swap_status": status_by_percent(swap_pct, 50, 80),
    }


def load_info():
    parts = Path('/proc/loadavg').read_text().split()[:3]
    values = [float(x) for x in parts]
    cores = os.cpu_count() or 1
    ratio = values[1] / cores * 100
    return {"values": values, "cores": cores, "ratio": ratio, "status": status_by_percent(ratio, 70, 100)}


def service_state(name):
    out = run(f"systemctl is-active {name} 2>/dev/null || true")
    return out or "unknown"


def parse_sadf_timestamp(text):
    raw = str(text).strip()
    if not raw:
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\s+(.+))?$", raw)
    if not m:
        return None
    base = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    zone_name = (m.group(2) or "").strip()
    zone_map = {
        "UTC": timezone.utc,
        "GMT": timezone.utc,
        "Z": timezone.utc,
        "CST": BJ,
        "Asia/Shanghai": BJ,
        "+08": BJ,
        "+0800": BJ,
        "+08:00": BJ,
    }
    tzinfo = zone_map.get(zone_name)
    if tzinfo is None and zone_name:
        try:
            tzinfo = ZoneInfo(zone_name)
        except Exception:
            tzinfo = LOCAL_TZ
    if tzinfo is None:
        tzinfo = LOCAL_TZ
    return base.replace(tzinfo=tzinfo)


def parse_sadf_table(cmd, timeout=30):
    out = run(cmd, timeout=timeout)
    rows = []
    headers = None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            maybe = line.lstrip('#').strip()
            if ';' in maybe:
                headers = [part.strip() for part in maybe.split(';')]
            continue
        if ';' not in line:
            continue
        parts = [part.strip() for part in line.split(';')]
        if headers and len(parts) == len(headers):
            rows.append(dict(zip(headers, parts)))
        else:
            rows.append({str(i): value for i, value in enumerate(parts)})
    return rows


def day_hour_aggregates():
    cpu_buckets = [{"sum": 0.0, "count": 0} for _ in range(24)]
    load_buckets = [{"sum": 0.0, "count": 0} for _ in range(24)]
    cpu_rows = parse_sadf_table("LC_ALL=C sadf -d -- -u ALL 2>/dev/null", timeout=60)
    for row in cpu_rows:
        if str(row.get('CPU')) not in ('all', '-1'):
            continue
        dt = parse_sadf_timestamp(row.get('timestamp', ''))
        if not dt:
            continue
        bj_dt = dt.astimezone(BJ)
        if bj_dt.date() != REPORT_DATE:
            continue
        try:
            busy = 100 - float(row.get('%idle', '100'))
        except Exception:
            continue
        bucket = cpu_buckets[bj_dt.hour]
        bucket['sum'] += busy
        bucket['count'] += 1

    load_rows = parse_sadf_table("LC_ALL=C sadf -d -- -q 2>/dev/null", timeout=60)
    for row in load_rows:
        dt = parse_sadf_timestamp(row.get('timestamp', ''))
        if not dt:
            continue
        bj_dt = dt.astimezone(BJ)
        if bj_dt.date() != REPORT_DATE:
            continue
        try:
            load1 = float(row.get('ldavg-1', row.get('ldavg-1m', '0')))
        except Exception:
            continue
        bucket = load_buckets[bj_dt.hour]
        bucket['sum'] += load1
        bucket['count'] += 1

    cpu_values = []
    cpu_counts = []
    load_values = []
    load_counts = []
    for hour in range(24):
        cpu_bucket = cpu_buckets[hour]
        load_bucket = load_buckets[hour]
        cpu_values.append(cpu_bucket['sum'] / cpu_bucket['count'] if cpu_bucket['count'] else 0.0)
        cpu_counts.append(cpu_bucket['count'])
        load_values.append(load_bucket['sum'] / load_bucket['count'] if load_bucket['count'] else 0.0)
        load_counts.append(load_bucket['count'])

    cpu_nonzero = [cpu_values[i] for i in range(24) if cpu_counts[i]]
    load_nonzero = [load_values[i] for i in range(24) if load_counts[i]]
    return {
        "cpu_values": cpu_values,
        "cpu_counts": cpu_counts,
        "cpu_avg": sum(cpu_nonzero) / len(cpu_nonzero) if cpu_nonzero else 0.0,
        "cpu_peak": max(cpu_nonzero) if cpu_nonzero else 0.0,
        "load_values": load_values,
        "load_counts": load_counts,
        "load_avg": sum(load_nonzero) / len(load_nonzero) if load_nonzero else 0.0,
        "load_peak": max(load_nonzero) if load_nonzero else 0.0,
    }


def vnstat_info():
    raw = run("vnstat --json 2>/dev/null", timeout=15)
    if not raw:
        return {"ok": False}
    try:
        data = json.loads(raw)
        interfaces = data.get("interfaces") or []
        if not interfaces:
            return {"ok": False}

        requested = str(CONFIG.network_interface or "").strip() if CONFIG else ""
        if requested:
            iface = next((item for item in interfaces if item.get("name") == requested), None)
        else:
            excluded_prefixes = ("br-", "docker", "veth", "lo")
            candidates = [
                item for item in interfaces
                if not str(item.get("name", "")).startswith(excluded_prefixes)
            ] or interfaces
            iface = max(candidates, key=lambda item: (item.get("traffic", {}).get("total", {}).get("rx", 0) or 0) + (item.get("traffic", {}).get("total", {}).get("tx", 0) or 0))

        if iface is None:
            return {"ok": False}
        traffic = iface.get("traffic", {})
        return {
            "ok": True,
            "name": iface.get("name", "unknown"),
            "total": traffic.get("total", {}),
            "days": traffic.get("day", []),
            "hours": traffic.get("hour", []),
        }
    except Exception:
        return {"ok": False}


def normalize_vn_hour(entry):
    try:
        timestamp = int(entry.get('timestamp') or 0)
    except Exception:
        timestamp = 0
    if timestamp:
        dt = datetime.fromtimestamp(timestamp, BJ)
    else:
        date_info = entry.get('date') or {}
        time_info = entry.get('time') or {}
        year = int(date_info.get('year', 0) or 0)
        month = int(date_info.get('month', 0) or 0)
        day = int(date_info.get('day', 0) or 0)
        hour = int(time_info.get('hour', 0) or 0)
        if not year or not month or not day:
            return None
        try:
            dt = datetime(year, month, day, hour, 0, 0, tzinfo=BJ)
        except Exception:
            return None
    return {
        "dt": dt,
        "hour": dt.hour,
        "rx": float(entry.get('rx', 0) or 0),
        "tx": float(entry.get('tx', 0) or 0),
    }


def daily_traffic_buckets(vn):
    buckets = [{"rx": 0.0, "tx": 0.0} for _ in range(24)]
    today_total = {"rx": 0.0, "tx": 0.0}
    yesterday_total = {"rx": 0.0, "tx": 0.0}
    if not vn.get('ok'):
        return {"buckets": buckets, "today": today_total, "yesterday": yesterday_total}

    for entry in vn.get('hours', []):
        item = normalize_vn_hour(entry)
        if not item:
            continue
        if item['dt'].date() == REPORT_DATE:
            buckets[item['hour']]['rx'] += item['rx']
            buckets[item['hour']]['tx'] += item['tx']

    for entry in vn.get('hours', []):
        item = normalize_vn_hour(entry)
        if not item:
            continue
        if item['dt'].date() == REPORT_DATE:
            today_total['rx'] += item['rx']
            today_total['tx'] += item['tx']
        elif item['dt'].date() == REPORT_DATE - timedelta(days=1):
            yesterday_total['rx'] += item['rx']
            yesterday_total['tx'] += item['tx']
    return {"buckets": buckets, "today": today_total, "yesterday": yesterday_total}


def docker_info():
    stats = []
    raw = run("docker stats --no-stream --format '{{json .}}' 2>/dev/null", timeout=60)
    for line in raw.splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue
        cpu = float(str(item.get("CPUPerc", "0")).replace('%', '') or 0)
        mem_usage = str(item.get("MemUsage", "0B / 0B")).split('/')[0].strip()
        mem = parse_size_to_bytes(mem_usage)
        net = str(item.get("NetIO", "0B / 0B")).split('/')
        rx = parse_size_to_bytes(net[0].strip()) if net else 0
        tx = parse_size_to_bytes(net[1].strip()) if len(net) > 1 else 0
        stats.append({"name": item.get("Name", ""), "cpu": cpu, "mem": mem, "rx": rx, "tx": tx})
    health = {}
    inspect = run("docker inspect --format '{{.Name}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $(docker ps -q) 2>/dev/null", timeout=30)
    for line in inspect.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            health[parts[0].lstrip('/')] = {"state": parts[1], "health": parts[2]}
    for item in stats:
        item.update(health.get(item["name"], {"state": "unknown", "health": "none"}))
    return stats


def log_usage():
    rows = []
    for name, path in (CONFIG.log_paths if CONFIG else []):
        out = run(f"du -sb {path} 2>/dev/null | cut -f1")
        try:
            size = int(out)
        except Exception:
            size = 0
        rows.append({"name": name, "path": path, "size": size})
    return rows


def security_alerts():
    since = time.time() - 86400
    records = []

    def parse_ts(value):
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").timestamp()
        except Exception:
            return 0

    if SECURITY_ALERT_DIR.exists():
        for path in sorted(SECURITY_ALERT_DIR.glob("attack-alert-*.log")):
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for line in lines:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                ts = parse_ts(str(record.get("ts", "")))
                if ts >= since:
                    records.append((ts, record))
    records.sort(key=lambda x: x[0])
    severity = Counter(r.get("severity", "UNKNOWN") for _, r in records)
    rules = Counter(r.get("rule", "unknown") for _, r in records)
    return {"records": records, "severity": severity, "rules": rules}


def timers_info():
    rows = []
    for name in (CONFIG.timer_units if CONFIG else []):
        active = run(f"systemctl is-active {name} 2>/dev/null || true") or "unknown"
        enabled = run(f"systemctl is-enabled {name} 2>/dev/null || true") or "unknown"
        rows.append({"name": name, "active": active, "enabled": enabled})
    return rows


def data_dirs():
    root = str(CONFIG.data_root if CONFIG else "/var/lib")
    out = run(f"du -xhd1 {root} 2>/dev/null | sort -hr | head -8", timeout=60)
    rows = []
    for line in out.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            display = parts[1].replace(root.rstrip('/') + '/', '')
            rows.append({"size": parts[0], "path": display})
    return rows


def public_ports():
    out = run("ss -ltnp 2>/dev/null | awk 'NR>1 && /LISTEN/ {print}'", timeout=15)
    rows = []
    for line in out.splitlines():
        if '0.0.0.0:' in line or '[::]:' in line:
            rows.append(line)
    return rows[:12]


def fail2ban_info():
    result = {"jails": [], "logs": []}
    status = run("fail2ban-client status 2>/dev/null", timeout=15)
    jail_names = []
    for line in status.splitlines():
        if 'Jail list:' in line:
            _, raw = line.split(':', 1)
            jail_names = [name.strip() for name in raw.split(',') if name.strip()]
            break

    for jail in jail_names:
        info = run(f"fail2ban-client status {jail} 2>/dev/null", timeout=15)
        row = {
            "name": jail,
            "currently_failed": '0',
            "total_failed": '0',
            "currently_banned": '0',
            "total_banned": '0',
            "banned_ips": '无',
        }
        for line in info.splitlines():
            if 'Currently failed:' in line:
                row['currently_failed'] = line.split(':', 1)[1].strip() or '0'
            elif 'Total failed:' in line:
                row['total_failed'] = line.split(':', 1)[1].strip() or '0'
            elif 'Currently banned:' in line:
                row['currently_banned'] = line.split(':', 1)[1].strip() or '0'
            elif 'Total banned:' in line:
                row['total_banned'] = line.split(':', 1)[1].strip() or '0'
            elif 'Banned IP list:' in line:
                value = line.split(':', 1)[1].strip()
                row['banned_ips'] = value or '无'
        result['jails'].append(row)

    log_lines = run("tail -n 80 /var/log/fail2ban.log 2>/dev/null", timeout=15).splitlines()
    for line in log_lines[-10:]:
        m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:,\d+)?\s+(\S+)\s+\[(.+?)\]\s+(.*)$", line)
        if not m:
            continue
        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=LOCAL_TZ).astimezone(BJ)
        jail = m.group(3)
        message = m.group(4)
        event = message
        jail_match = re.search(r"\[(.+?)\]", message)
        if jail_match:
            jail = jail_match.group(1)
            event = re.sub(r"\s*\[.+?\]\s*", "", message, count=1)
        result['logs'].append({
            "time": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "level": m.group(2),
            "jail": jail,
            "event": event,
        })
    return result


def collect_report_data(config):
    global BJ, REPORT_DATE, LOCAL_TZ, SECURITY_ALERT_DIR, CONFIG
    CONFIG = config
    BJ = config.bj
    REPORT_DATE = config.report_date
    LOCAL_TZ = config.local_tz
    SECURITY_ALERT_DIR = config.security_alert_dir

    vn = vnstat_info()
    traffic = daily_traffic_buckets(vn)
    return {
        "mem": mem_info(),
        "load": load_info(),
        "daily": day_hour_aggregates(),
        "vn": vn,
        "traffic": traffic,
        "docker": docker_info(),
        "logs": log_usage(),
        "security": security_alerts(),
        "timers": timers_info(),
        "fail2ban_detail": fail2ban_info(),
        "root_disk": disk_usage(config.root_disk_path),
        "data_disk": disk_usage(config.data_disk_path),
        "fail2ban": service_state('fail2ban'),
        "sysstat": service_state('sysstat.service'),
        "vnstat": service_state('vnstat.service'),
        "data_dir_detail": data_dirs(),
        "public_port_rows": public_ports(),
    }
