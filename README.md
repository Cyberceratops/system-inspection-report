# System Inspection Report

System Inspection Report 是一个 Linux 每日巡检报告生成器，会采集 CPU、Load、内存、Swap、磁盘、vnStat 流量、Docker 容器、systemd 定时任务、fail2ban 和本地安全事件，并生成一份 HTML 报告和文本摘要。投递渠道支持 email 和 Telegram。

## 特性

- 生成高对比度 HTML 巡检报告。
- 支持 systemd timer 定时执行。
- 支持 sysstat/sadf 的 CPU 和 Load 小时趋势。
- 支持 vnStat 网络流量统计，自动排除 Docker bridge/veth/lo，也可指定网卡。
- 支持 Docker 容器资源 Top、健康检查状态和日志目录占用。
- 支持 Telegram summary + HTML document 分别投递。
- 支持 `best-effort` 和 `strict` 投递语义。
- 默认不发送任何外部消息，必须显式配置投递开关。

## 依赖

必需：

- Linux
- Python 3.11+
- systemd

可选但推荐：

- `sysstat`：CPU / Load 小时趋势
- `vnstat`：网卡流量统计
- `docker`：容器资源和健康状态
- `fail2ban`：防护状态和最近日志
- `mail`：email 投递
- `curl`：Telegram 投递

## 快速试跑

```bash
cd system-inspection-report
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
SEND_EMAIL=0 SEND_TELEGRAM=0 REPORT_DIR=reports system-inspection-report root
```

生成文件位于 `reports/`：

- `inspection-YYYY-MM-DD-HHMMSS.html`
- `inspection-YYYY-MM-DD-HHMMSS.summary.txt`

## 配置

可以通过环境变量和 JSON 配置文件控制行为。环境变量优先级高于 JSON 配置。

示例：

```bash
cp examples/env.example /etc/system-inspection-report.env
cp examples/config.example.json /etc/system-inspection-report.json
chmod 600 /etc/system-inspection-report.env
```

关键环境变量：

| 变量 | 含义 | 默认值 |
| --- | --- | --- |
| `REPORT_TZ` | 报告时区 | `Asia/Shanghai` |
| `REPORT_DIR` | 报告输出目录 | `reports` |
| `SYSTEM_INSPECTION_CONFIG` | JSON 配置路径 | 空 |
| `REPORT_NET_IFACE` | 指定 vnStat 网卡 | 自动选择非 Docker 接口 |
| `SEND_EMAIL` | 是否发送 email | `0` |
| `SEND_TELEGRAM` | 是否发送 Telegram | `0` |
| `DELIVERY_MODE` | `best-effort` 或 `strict` | `best-effort` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | 空 |
| `TELEGRAM_CHAT_ID` | Telegram chat id | 空 |
| `ROOT_DISK_PATH` | 根分区统计路径 | `/` |
| `DATA_DISK_PATH` | 数据盘统计路径 | `/var/lib` |
| `DATA_ROOT` | 数据目录明细根路径 | `/var/lib` |

JSON 配置可设置：

- `log_paths`：日志空间占用列表，例如 `["System logs", "/var/log"]`
- `timer_units`：要展示的 systemd timer/service 列表
- `security_alert_dir`：本地安全事件 JSONL 目录
- `root_disk_path`、`data_disk_path`、`data_root`
- `network_interface`

## systemd 安装示例

```bash
sudo mkdir -p /opt/system-inspection-report
sudo rsync -a ./ /opt/system-inspection-report/
sudo cp examples/env.example /etc/system-inspection-report.env
sudo cp examples/config.example.json /etc/system-inspection-report.json
sudo chmod 600 /etc/system-inspection-report.env
sudo cp examples/system-inspection-report.service /etc/systemd/system/
sudo cp examples/system-inspection-report.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now system-inspection-report.timer
```

手动执行一次：

```bash
sudo systemctl start system-inspection-report.service
sudo journalctl -u system-inspection-report.service -n 100 --no-pager
```

## 投递语义

- `DELIVERY_MODE=best-effort`：报告生成成功即返回成功，投递失败写 stderr/journal。
- `DELIVERY_MODE=strict`：启用的投递渠道失败时返回非零。

Telegram 会分别发送：

1. 文本摘要
2. HTML 报告附件

两者失败会分别记录，便于排查。

## 安全与脱敏

开源仓库不应包含：

- `*.env` 或真实环境文件
- Telegram token / chat id
- 真实 HTML 报告和 summary
- 真实主机名、IP、端口清单截图
- 业务内部服务名、目录名、备份文件

报告本身可能包含监听端口、容器名、日志路径和 systemd 单元名称。公开截图或报告样例前请先脱敏。

## 许可证

MIT
