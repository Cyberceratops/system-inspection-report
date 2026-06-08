def status_by_percent(value, warn, crit, inverse=False):
    if inverse:
        if value <= crit:
            return "CRIT"
        if value <= warn:
            return "WARN"
        return "OK"
    if value >= crit:
        return "CRIT"
    if value >= warn:
        return "WARN"
    return "OK"

def overall_status(*states):
    if 'CRIT' in states:
        return 'CRIT'
    if 'WARN' in states:
        return 'WARN'
    return 'OK'

def assess_report(data):
    mem = data["mem"]
    load = data["load"]
    daily = data["daily"]
    docker = data["docker"]
    security = data["security"]
    root_disk = data["root_disk"]
    fail2ban = data["fail2ban"]
    sysstat = data["sysstat"]
    vnstat = data["vnstat"]

    cpu_busy = daily['cpu_avg'] if daily['cpu_avg'] > 0 else max(0, min(100, load['ratio']))
    cpu_status = status_by_percent(cpu_busy, 70, 90)
    unhealthy = [c for c in docker if c.get('health') not in ('healthy', 'none') or c.get('state') != 'running']
    container_status = 'CRIT' if unhealthy else 'OK'
    security_status = 'CRIT' if security['severity'].get('CRIT') else 'WARN' if security['severity'].get('WARN') else 'OK'
    monitor_status = 'OK' if sysstat == 'active' and vnstat == 'active' else 'WARN'
    fail2ban_status = 'OK' if fail2ban == 'active' else 'CRIT'

    issues = []
    if load['status'] != 'OK':
        issues.append(f"负载偏高：5 分钟负载 {load['values'][1]:.2f} / {load['cores']} 核")
    if mem['swap_status'] != 'OK':
        issues.append(f"Swap 使用偏高：{mem['swap_pct']:.0f}%")
    if root_disk['status'] != 'OK':
        issues.append(f"根分区空间偏高：{root_disk['pct']:.0f}%")
    if unhealthy:
        issues.append(f"容器异常：{len(unhealthy)} 个")
    if security_status != 'OK':
        issues.append(f"安全告警：CRIT {security['severity'].get('CRIT', 0)} / WARN {security['severity'].get('WARN', 0)}")
    if fail2ban_status != 'OK':
        issues.append("Fail2ban 服务异常")
    if not issues:
        issues.append("整体运行稳定，未发现需要立即处理的问题")

    verdict_status = overall_status(
        cpu_status if load['status'] == 'CRIT' else 'OK',
        mem['swap_status'],
        root_disk['status'],
        container_status,
        security_status,
        fail2ban_status,
        monitor_status,
    )
    verdict_note = {
        'OK': '核心指标稳定，采样与防护服务正常。',
        'WARN': f'{len(issues)} 项需要关注，其余指标保持可用。',
        'CRIT': f'{len(issues)} 项需要立即处理，请优先核查异常服务与容量。',
    }[verdict_status]

    return {
        "cpu_busy": cpu_busy,
        "cpu_status": cpu_status,
        "unhealthy": unhealthy,
        "container_status": container_status,
        "security_status": security_status,
        "monitor_status": monitor_status,
        "fail2ban_status": fail2ban_status,
        "issues": issues,
        "verdict_status": verdict_status,
        "verdict_note": verdict_note,
    }

