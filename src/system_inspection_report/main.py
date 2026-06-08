#!/usr/bin/env python3
import sys
from pathlib import Path

from .assess import assess_report
from .collectors import collect_report_data
from .config import load_config
from .delivery import deliver_report
from .renderer import prepare_template_context, render_report, render_summary


def main():
    config = load_config()
    data = collect_report_data(config)
    assessment = assess_report(data)

    config.summary_file.write_text(render_summary(config, data, assessment), encoding="utf-8")
    context = prepare_template_context(config, data, assessment)
    html_doc = render_report(Path(__file__).resolve().parent / "templates", context)
    config.report_file.write_text(html_doc, encoding="utf-8")

    delivery_failures = deliver_report(config)
    if delivery_failures and config.delivery_mode == "strict":
        return 1

    print(config.report_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
