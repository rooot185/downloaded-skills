"""Fill 夜班 / 加班 / 出勤天数 on a punch-time workbook."""

import argparse
import re
import sys
from copy import copy
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook

RESULT_HEADERS = ("夜班", "加班", "出勤天数")
TIME_RE = re.compile(r"(\d{1,2}:\d{2})")
RANGE_RE = re.compile(
    r"统计日期：\s*(\d{4}-\d{2}-\d{2})\s*至\s*(\d{4}-\d{2}-\d{2})"
)


def configure_stdout():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def parse_dates(values):
    found = []
    for raw in values or []:
        for part in str(raw).split(","):
            part = part.strip()
            if not part:
                continue
            found.append(datetime.strptime(part, "%Y-%m-%d").date())
    return found


def minutes(text):
    hour, minute = text.split(":")
    return int(hour) * 60 + int(minute)


def night_count(times):
    if len(times) < 2:
        return 0
    first, last = minutes(times[0]), minutes(times[-1])
    if first >= 17 * 60 + 30:
        return 0
    count = 1 if first <= 7 * 60 + 30 else 0
    if 17 * 60 + 30 <= last <= 20 * 60:
        count += 1
    elif 20 * 60 + 1 <= last <= 22 * 60:
        count += 2
    elif last > 22 * 60:
        return None
    return count


def overtime_days(day, is_overtime):
    if not is_overtime or not day[1]:
        return 0
    times = day[1]
    if len(times) == 1:
        return 0.5
    if minutes(times[-1]) - minutes(times[0]) >= 4 * 60:
        return 1
    return 0.5


def as_number(value):
    if float(value).is_integer():
        return int(value)
    return float(value)


def sheet_results(ws):
    found = {}
    for row in ws.iter_rows(min_row=1, max_row=min(12, ws.max_row or 1)):
        for cell in row:
            if cell.value is None:
                continue
            text = str(cell.value).strip()
            if text in RESULT_HEADERS and text not in found:
                found[text] = (cell.row, cell.column)
    if set(found) != set(RESULT_HEADERS):
        return None
    rows = {pos[0] for pos in found.values()}
    if len(rows) != 1:
        raise SystemExit(f"{ws.title} 的夜班、加班、出勤天数不在同一行")
    return found


def stat_range(ws):
    for row in ws.iter_rows(min_row=1, max_row=min(5, ws.max_row or 1)):
        for cell in row:
            if cell.value is None:
                continue
            match = RANGE_RE.search(str(cell.value))
            if match:
                start = datetime.strptime(match.group(1), "%Y-%m-%d").date()
                end = datetime.strptime(match.group(2), "%Y-%m-%d").date()
                return start, end
    return None


def name_column(ws):
    for row in ws.iter_rows(min_row=1, max_row=min(8, ws.max_row or 1)):
        for cell in row:
            if cell.value is not None and str(cell.value).strip() == "姓名":
                return cell.column
    raise SystemExit(f"{ws.title} 找不到「姓名」列")


def date_columns(ws, header_row, result_columns):
    stop = min(result_columns)
    start_col = None
    for col in range(1, stop):
        value = ws.cell(header_row, col).value
        if value is not None and str(value).strip():
            start_col = col
            break
    if start_col is None:
        raise SystemExit(f"{ws.title} 找不到日期列")
    return list(range(start_col, stop))


def punch_times(value):
    if value is None or str(value).strip() == "":
        return []
    times = TIME_RE.findall(str(value))
    if not times:
        raise ValueError(repr(value))
    return times


def style_source(ws, rows, columns):
    for row in rows:
        for col in columns:
            cell = ws.cell(row, col)
            if cell.value not in (None, "") and cell.font is not None and cell.font.name:
                return cell
    return None


def apply_style(cell, source):
    if source is None:
        return
    cell.font = copy(source.font)
    cell.alignment = copy(source.alignment)
    cell.border = copy(source.border)
    cell.number_format = "General"


def choose_sheet(wb, sheet_name):
    matched = [name for name in wb.sheetnames if sheet_results(wb[name])]
    if sheet_name:
        if sheet_name not in wb.sheetnames:
            raise SystemExit(f"没有工作表：{sheet_name}")
        if sheet_name not in matched:
            raise SystemExit(f"{sheet_name} 没有夜班、加班、出勤天数表头")
        return wb[sheet_name]
    if len(matched) == 1:
        return wb[matched[0]]
    if not matched:
        raise SystemExit("没有工作表同时包含夜班、加班、出勤天数。先确认要写到哪一张，不要自行加表头。")
    raise SystemExit("多张表都有这三列，请用 --sheet 指定：" + "、".join(matched))


def save_workbook(wb, path):
    try:
        wb.save(path)
        return path
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_已填写{path.suffix}")
        wb.save(fallback)
        print(f"原文件被占用，已另存为 {fallback}")
        return fallback


def fill(path, normal_days, extra_overtime, sheet_name, dry_run):
    wb = load_workbook(path)
    ws = choose_sheet(wb, sheet_name)
    found = sheet_results(ws)
    header_row = found["夜班"][0]
    columns = date_columns(ws, header_row, [pos[1] for pos in found.values()])
    span = stat_range(ws)
    if span is None:
        raise SystemExit(f"{ws.title} 标题里没有「统计日期：YYYY-MM-DD 至 YYYY-MM-DD」")
    start, title_end = span
    days = [start + timedelta(days=offset) for offset in range(len(columns))]
    notes = []
    if days[-1] != title_end:
        notes.append(
            f"标题截止日期是 {title_end.isoformat()}，日期列实际算到 {days[-1].isoformat()}"
        )
    outside = [day for day in normal_days + extra_overtime if day < days[0] or day > days[-1]]
    if outside:
        notes.append("这些例外日期不在表内：" + "、".join(day.isoformat() for day in outside))
    weekend = {day for day in days if day.weekday() >= 5}
    overtime = (weekend - set(normal_days)) | set(extra_overtime)

    name_col = name_column(ws)
    records = []
    late_departures = []
    for row in range(header_row + 1, ws.max_row + 1):
        name = ws.cell(row, name_col).value
        if name is None or str(name).strip() == "":
            continue
        night = overtime_total = attendance = 0
        for col, day in zip(columns, days):
            try:
                times = punch_times(ws.cell(row, col).value)
            except ValueError as exc:
                raise SystemExit(f"{name} {day.isoformat()} 无法识别打卡时间：{exc}") from exc
            if not times:
                continue
            counted = night_count(times)
            if counted is None:
                late_departures.append(f"{name} {day.isoformat()} 下班 {times[-1]}")
                counted = 0
            night += counted
            overtime_total += overtime_days((day, times), day in overtime)
            attendance += 1
        records.append((row, str(name).strip(), night, as_number(overtime_total), attendance))

    if late_departures:
        raise SystemExit(
            "下班晚于 22:00，当前规则没有这一档，请先确认后再计算：\n"
            + "\n".join(late_departures)
        )

    if not dry_run:
        source = style_source(ws, [item[0] for item in records], columns)
        for row, _name, night, overtime_total, attendance in records:
            for key, value in zip(RESULT_HEADERS, (night, overtime_total, attendance)):
                cell = ws.cell(row, found[key][1], value)
                apply_style(cell, source)
        saved = save_workbook(wb, path)
    else:
        saved = path

    print(f"工作表\t{ws.title}")
    print(f"文件\t{saved}")
    print(f"日期\t{days[0].isoformat()} 至 {days[-1].isoformat()}，共 {len(days)} 天")
    print(
        "不计加班\t"
        + ("、".join(day.isoformat() for day in sorted(set(normal_days))) or "无")
    )
    print(
        "额外加班日\t"
        + ("、".join(day.isoformat() for day in sorted(set(extra_overtime))) or "无")
    )
    for note in notes:
        print(f"说明\t{note}")
    print("姓名\t夜班\t加班\t出勤天数")
    for _row, name, night, overtime_total, attendance in records:
        print(f"{name}\t{night}\t{overtime_total}\t{attendance}")


def main():
    configure_stdout()
    parser = argparse.ArgumentParser(description="填写夜班、加班、出勤天数")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--normal-days", action="append", default=[])
    parser.add_argument("--overtime-days", action="append", default=[])
    parser.add_argument("--sheet")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    fill(
        args.workbook,
        parse_dates(args.normal_days),
        parse_dates(args.overtime_days),
        args.sheet,
        args.dry_run,
    )


if __name__ == "__main__":
    main()
