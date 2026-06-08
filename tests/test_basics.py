from system_inspection_report.assess import status_by_percent
from system_inspection_report.renderer import compute_axis_max


def test_status_by_percent():
    assert status_by_percent(10, 70, 90) == "OK"
    assert status_by_percent(75, 70, 90) == "WARN"
    assert status_by_percent(95, 70, 90) == "CRIT"


def test_percent_axis_is_dynamic():
    assert compute_axis_max([3.2], minimum=1, percent=True) == 4
    assert compute_axis_max([34.5], minimum=1, percent=True) == 40
