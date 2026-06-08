import html
import math
import re
from pathlib import Path


TODAY = ""


def render_report(template_dir, context):
    template = (Path(template_dir) / "report.html").read_text(encoding="utf-8")
    source = "f'''" + template.replace("'''", "\\'\\'\\'") + "'''"
    return eval(source, context, context)


def esc(value):
    return html.escape(str(value), quote=True)


def clamp(value, lo=0, hi=100):
    return max(lo, min(hi, value))


def fmt_bytes(num):
    try:
        num = float(num)
    except Exception:
        return "-"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    idx = 0
    while abs(num) >= 1024 and idx < len(units) - 1:
        num /= 1024
        idx += 1
    if idx == 0:
        return f"{num:.0f}{units[idx]}"
    return f"{num:.1f}{units[idx]}"


def fmt_bytes_spaced(num):
    text = fmt_bytes(num)
    return re.sub(r"(?<=\d)(?=[A-Za-z])", " ", text)


def metric_card(title, value, sub, status="OK", progress=None, accent=None):
    style = f' style="color:{accent}"' if accent else ''
    progress_html = ''
    if progress is not None:
        progress_html = f'<div class="bar"><span class="{status}" style="width:{clamp(progress):.1f}%"></span></div>'
    return (
        f'<article class="metric">'
        f'<div class="metric-top"><h3>{esc(title)}</h3><span class="pill {status}">{status}</span></div>'
        f'<strong{style}>{esc(value)}</strong>'
        f'<p>{esc(sub)}</p>'
        f'{progress_html}'
        f'</article>'
    )


def x_axis_day_labels():
    labels = []
    for hour in range(24):
        labels.append(f"{hour:02d}" if hour in (0, 4, 8, 12, 16, 20, 23) else "")
    return ''.join(f'<span>{label}</span>' for label in labels)


def compute_axis_max(values, minimum=1.0, percent=False):
    peak = max(values) if values else 0.0
    if percent:
        padded = max(peak * 1.15, minimum)
        if padded <= 10:
            step = 1
        elif padded <= 30:
            step = 5
        else:
            step = 10
        return min(100, max(math.ceil(padded / step) * step, minimum))
    padded = max(peak * 1.15, minimum)
    if padded <= 2:
        step = 0.25
    elif padded <= 5:
        step = 0.5
    else:
        step = 1.0
    return max(math.ceil(padded / step) * step, minimum)


def axis_label_text(value, suffix=""):
    if suffix == '%':
        return f"{value:.0f}%"
    if value <= 0:
        return '0'
    if value >= 10:
        return f"{value:.1f}".rstrip('0').rstrip('.')
    return f"{value:.2f}".rstrip('0').rstrip('.')


def axis_chart(values, counts, max_value, kind="cpu", suffix="", decimals=1, hot_threshold=None):
    bars = []
    for hour, value in enumerate(values):
        height = 0 if max_value <= 0 else (value / max_value * 100)
        hot = hot_threshold is not None and value >= hot_threshold and counts[hour] > 0
        cls = 'hour-bar hot' if hot else 'hour-bar'
        display = f"{value:.{decimals}f}{suffix}"
        title = f"{TODAY} {hour:02d}:00 · {display} · {counts[hour]} 个采样"
        bars.append(f'<div class="{cls}" title="{esc(title)}"><span style="height:{clamp(height):.1f}%"></span></div>')
    y_values = [max_value * step / 5 for step in range(5, -1, -1)]
    return (
        f'<div class="axis-chart {kind}" aria-label="{esc(kind)} 24 小时柱状图">'
        f'<div class="y-axis">{"".join(f"<span>{esc(axis_label_text(v, suffix))}</span>" for v in y_values)}</div>'
        f'<div class="plot"><div class="hour-bars">{"".join(bars)}</div></div>'
        f'<div class="x-axis">{x_axis_day_labels()}</div>'
        f'</div>'
    )


def integer_axis_step(raw_step):
    if raw_step <= 1:
        return 1
    magnitude = 10 ** math.floor(math.log10(raw_step))
    for multiplier in (1, 2, 5, 10):
        step = multiplier * magnitude
        if step >= raw_step:
            return int(step)
    return int(10 * magnitude)


def traffic_axis(values):
    peak = max(values or [0])
    gib = 1024 ** 3
    mib = 1024 ** 2
    kib = 1024
    if peak >= 10 * gib:
        unit_name, unit_size = "GiB", gib
    elif peak >= mib:
        unit_name, unit_size = "MiB", mib
    elif peak >= kib:
        unit_name, unit_size = "KiB", kib
    else:
        unit_name, unit_size = "B", 1
    padded_units = max(peak * 1.15 / unit_size, 1)
    step_units = integer_axis_step(padded_units / 5)
    return step_units * 5 * unit_size, step_units, unit_name


def traffic_chart(buckets):
    totals = [item['rx'] + item['tx'] for item in buckets]
    max_value, step_units, unit_name = traffic_axis(totals)
    bars = []
    peak = max(totals or [0])
    for hour, item in enumerate(buckets):
        rx = item['rx']
        tx = item['tx']
        total = rx + tx
        rx_height = 0 if max_value <= 0 else rx / max_value * 100
        tx_height = 0 if max_value <= 0 else tx / max_value * 100
        cls = 'traffic-stack hot' if peak and total >= peak * 0.75 else 'traffic-stack'
        title = f"{TODAY} {hour:02d}:00 · 下行 {fmt_bytes(rx)} · 上行 {fmt_bytes(tx)} · 合计 {fmt_bytes(total)}"
        bars.append(
            f'<div class="{cls}" title="{esc(title)}">'
            f'<span class="tx" style="height:{clamp(tx_height):.1f}%"></span>'
            f'<span class="rx" style="height:{clamp(rx_height):.1f}%"></span>'
            f'</div>'
        )
    y_values = [step_units * step for step in range(5, -1, -1)]
    y_html = ''.join(f'<span>{esc(f"{value}{unit_name}" if value else "0")}</span>' for value in y_values)
    return (
        f'<div class="traffic-chart" aria-label="网卡 24 小时上下行流量堆叠柱状图">'
        f'<div class="y-axis">{y_html}</div>'
        f'<div class="traffic-plot"><div class="traffic-bars">{"".join(bars)}</div></div>'
        f'<div class="x-axis">{x_axis_day_labels()}</div>'
        f'</div>'
    )


def rank_rows(rows, kind):
    if not rows:
        return '<div class="empty">暂无数据</div>'
    if kind == 'cpu':
        max_value = max([r['cpu'] for r in rows] + [1])
    elif kind == 'mem':
        max_value = max([r['mem'] for r in rows] + [1])
    else:
        max_value = max([r['rx'] + r['tx'] for r in rows] + [1])
    html_rows = []
    for r in rows:
        if kind == 'cpu':
            width = r['cpu'] / max_value * 100
        elif kind == 'mem':
            width = r['mem'] / max_value * 100
        else:
            width = (r['rx'] + r['tx']) / max_value * 100
        html_rows.append(
            f'<div class="rank-row">'
            f'<div><b>{esc(r["name"])}</b><small>{esc(r.get("health", ""))}</small></div>'
            f'<div class="bar slim"><span style="width:{clamp(width):.1f}%"></span></div>'
            f'</div>'
        )
    return ''.join(html_rows)


def log_rows(rows):
    if not rows:
        return '<div class="empty">暂无数据</div>'
    peak = max([r['size'] for r in rows] + [1])
    out = []
    for r in rows:
        out.append(
            f'<div class="rank-row">'
            f'<div><b>{esc(r["name"])}</b><small>{esc(r["path"])}</small></div>'
            f'<div class="bar slim"><span style="width:{r["size"] / peak * 100:.1f}%"></span></div>'
            f'</div>'
        )
    return ''.join(out)


def timer_rows(rows):
    return ''.join(
        f'<tr><td>{esc(r["name"])}</td><td><span class="pill {"OK" if r["active"] == "active" else "WARN"}">{esc(r["active"])}</span></td><td>{esc(r["enabled"])}</td></tr>'
        for r in rows
    )


def container_table(rows):
    out = []
    for c in sorted(rows, key=lambda x: x['name']):
        health = c.get('health', 'none')
        status = 'OK' if c.get('state') == 'running' and health in ('healthy', 'none') else 'CRIT'
        out.append(
            f'<tr><td>{esc(c["name"])}</td><td><span class="pill {status}">{esc(health)}</span></td><td>{c["cpu"]:.1f}%</td><td>{esc(fmt_bytes(c["mem"]))}</td><td>{esc(fmt_bytes(c["rx"] + c["tx"]))}</td></tr>'
        )
    return ''.join(out)


def render_summary(config, data, assessment):
    mem = data["mem"]
    load = data["load"]
    root_disk = data["root_disk"]
    data_disk = data["data_disk"]
    traffic = data["traffic"]
    vn = data["vn"]
    docker = data["docker"]
    issues = assessment["issues"]
    unhealthy = assessment["unhealthy"]
    cpu_busy = assessment["cpu_busy"]
    return f"""环境巡检摘要
主机: {config.host_name}
时间: {config.now}
结论: {issues[0]}
CPU: 当日小时均值 {cpu_busy:.1f}% / Load {load['values'][0]:.2f} {load['values'][1]:.2f} {load['values'][2]:.2f}
内存: {fmt_bytes(mem['used'])}/{fmt_bytes(mem['total'])} ({mem['pct']:.0f}%)
Swap: {fmt_bytes(mem['swap_used'])}/{fmt_bytes(mem['swap_total'])} ({mem['swap_pct']:.0f}%)
磁盘: / {root_disk['pct']:.0f}% / data {data_disk['pct']:.0f}%
流量: 今日 {fmt_bytes(traffic['today']['rx'] + traffic['today']['tx'])} / 累计 {fmt_bytes((vn.get('total', {}) or {}).get('rx', 0) + (vn.get('total', {}) or {}).get('tx', 0))}
容器: {len(docker)} 个运行中，异常 {len(unhealthy)} 个
监控: sysstat={data['sysstat']}, vnstat={data['vnstat']}
完整 HTML 报告见附件。
"""


def prepare_template_context(config, data, assessment):
    global TODAY
    TODAY = config.today
    mem = data["mem"]
    load = data["load"]
    daily = data["daily"]
    vn = data["vn"]
    traffic = data["traffic"]
    docker = data["docker"]
    logs = data["logs"]
    security = data["security"]
    timers = data["timers"]
    fail2ban_detail = data["fail2ban_detail"]
    root_disk = data["root_disk"]
    data_disk = data["data_disk"]
    fail2ban = data["fail2ban"]
    sysstat = data["sysstat"]
    vnstat = data["vnstat"]

    cpu_busy = assessment["cpu_busy"]
    cpu_status = assessment["cpu_status"]
    unhealthy = assessment["unhealthy"]
    container_status = assessment["container_status"]
    security_status = assessment["security_status"]
    monitor_status = assessment["monitor_status"]
    fail2ban_status = assessment["fail2ban_status"]
    issues = assessment["issues"]
    verdict_status = assessment["verdict_status"]
    verdict_note = assessment["verdict_note"]

    top_cpu = sorted(docker, key=lambda x: x['cpu'], reverse=True)[:6]
    top_mem = sorted(docker, key=lambda x: x['mem'], reverse=True)[:6]
    top_net = sorted(docker, key=lambda x: x['rx'] + x['tx'], reverse=True)[:6]
    log_top = sorted(logs, key=lambda x: x['size'], reverse=True)[:6]
    traffic_today = traffic['today']['rx'] + traffic['today']['tx']
    traffic_yesterday = traffic['yesterday']['rx'] + traffic['yesterday']['tx']
    traffic_total = ((vn.get('total', {}) or {}).get('rx', 0) + (vn.get('total', {}) or {}).get('tx', 0)) if vn.get('ok') else 0
    traffic_buckets = traffic['buckets']
    traffic_peak = max([(item['rx'] + item['tx']) for item in traffic_buckets] + [0])
    cpu_sample_count = sum(daily['cpu_counts'])
    if cpu_sample_count:
        cpu_chart_values = daily['cpu_values']
        cpu_chart_counts = daily['cpu_counts']
        cpu_peak_display = daily['cpu_peak']
        cpu_source_note = '小时采样'
    else:
        cpu_chart_values = [0.0 for _ in range(24)]
        cpu_chart_counts = [0 for _ in range(24)]
        cpu_chart_values[config.report_now.hour] = cpu_busy
        cpu_chart_counts[config.report_now.hour] = 1
        cpu_peak_display = cpu_busy
        cpu_source_note = 'CPU 小时采样不足，当前柱按 Load/核数估算'
    cpu_axis_max = compute_axis_max(cpu_chart_values, minimum=1, percent=True)
    load_sample_count = sum(daily['load_counts'])
    load_peak_display = daily['load_peak'] if load_sample_count else load['values'][0]
    load_axis_values = daily['load_values'] if load_sample_count else [load['values'][0]]
    load_axis_max = compute_axis_max(load_axis_values, minimum=1.0)
    window_label = f"{config.today} 00:00:00—23:59:59 北京时间"

    fail2ban_jail_rows = ''.join(
        f'<tr><td>{esc(item["name"])}</td><td>{esc(item["currently_failed"])}</td><td>{esc(item["total_failed"])}</td><td>{esc(item["currently_banned"])}</td><td>{esc(item["total_banned"])}</td><td>{esc(item["banned_ips"])}</td></tr>'
        for item in fail2ban_detail['jails']
    ) or '<tr><td>无</td><td>0</td><td>0</td><td>0</td><td>0</td><td>无</td></tr>'
    fail2ban_log_rows = ''.join(
        f'<tr><td>{esc(item["time"])}</td><td>{esc(item["level"])}</td><td>{esc(item["jail"])}</td><td>{esc(item["event"])}</td></tr>'
        for item in fail2ban_detail['logs']
    ) or '<tr><td>无</td><td>-</td><td>-</td><td>暂无最近日志</td></tr>'
    security_rule_rows = ''.join(
        f'<tr><td>{esc(k)}</td><td>{v}</td></tr>' for k, v in security['rules'].most_common(10)
    ) or '<tr><td>无异常威胁事件</td><td>0</td></tr>'
    data_dir_rows = ''.join(
        f'<tr><td>{esc(r["size"])}</td><td>{esc(r["path"])}</td></tr>' for r in data["data_dir_detail"]
    ) or '<tr><td>无</td><td>暂无数据</td></tr>'
    public_port_rows = ''.join(
        f'<tr><td>{esc(x)}</td></tr>' for x in data["public_port_rows"]
    ) or '<tr><td>暂无公开监听端口</td></tr>'

    context = dict(locals())
    context.update({
        "HOST_NAME": config.host_name,
        "NOW": config.now,
        "TODAY": config.today,
        "esc": esc,
        "metric_card": metric_card,
        "axis_chart": axis_chart,
        "traffic_chart": traffic_chart,
        "rank_rows": rank_rows,
        "log_rows": log_rows,
        "timer_rows": timer_rows,
        "container_table": container_table,
        "fmt_bytes": fmt_bytes,
        "fmt_bytes_spaced": fmt_bytes_spaced,
        "max": max,
        "len": len,
    })
    return context
