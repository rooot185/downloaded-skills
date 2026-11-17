"""Fill 实际加班数 and 实际夜班数 from punch totals and the sheet's average-rate formula."""

import argparse
import re
import sys
from pathlib import Path

from openpyxl import load_workbook

FORMULA_RE = re.compile(
    r"^=\(([A-Z]+\d+)\+\((\d+)-([A-Z]+\d+)\)\*5-([A-Z]+\d+)-([A-Z]+\d+)([+-]\d+(?:\.\d+)?)\)/([A-Z]+\d+)$"
)
NUMBER_RE = re.compile(r"[0-9.+\-]+")


def configure_stdout():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def compact(value):
    return re.sub(r"\s+", "", str(value or ""))


def numeric_expr(value):
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.startswith("="):
        text = text[1:].replace(" ", "")
    if NUMBER_RE.fullmatch(text):
        return float(eval(text, {"__builtins__": {}}))
    raise ValueError(repr(value))


def find_header_row(ws):
    for row in range(1, 16):
        texts = []
        for col in range(1, 40):
            value = ws.cell(row, col).value
            if value is not None:
                texts.append(compact(value))
        if "姓名" in texts and "实际加班数" in texts and "实际夜班数" in texts:
            return row
    raise SystemExit(f"{ws.title} 找不到姓名、实际加班数、实际夜班数表头")


def header_columns(ws, header_row):
    found = {}
    for col in range(1, 40):
        value = ws.cell(header_row, col).value
        if value is None:
            continue
        found.setdefault(compact(value), col)
    required = ("姓名", "实际加班数", "实际夜班数", "夜班标准", "基本薪酬", "上月余额")
    missing = [name for name in required if name not in found]
    if missing:
        raise SystemExit(f"{ws.title} 缺少表头：" + "、".join(missing))
    return found


def employee_rows(ws, header_row, name_col):
    rows = []
    for row in range(header_row + 1, header_row + 40):
        name = ws.cell(row, name_col).value
        if name is None or compact(name) == "":
            break
        if compact(name) == "合计":
            break
        rows.append(row)
    if not rows:
        raise SystemExit(f"{ws.title} 没有员工行")
    return rows


def average_formula(ws):
    for row in ws.iter_rows(min_row=1, max_row=45, max_col=20):
        for cell in row:
            if not isinstance(cell.value, str) or not cell.value.startswith("="):
                continue
            match = FORMULA_RE.fullmatch(cell.value.replace(" ", ""))
            if match:
                return cell.coordinate, match
    raise SystemExit(f"{ws.title} 找不到可识别的平均加班费公式")


def punch_totals(path, sheet_name):
    wb = load_workbook(path, data_only=False)
    matched = []
    for name in wb.sheetnames:
        ws = wb[name]
        headers = {}
        for row in ws.iter_rows(min_row=1, max_row=8, max_col=45):
            for cell in row:
                if cell.value is not None:
                    headers.setdefault(compact(cell.value), (cell.row, cell.column))
        if "夜班" in headers and "加班" in headers and "姓名" in headers:
            matched.append((name, ws, headers))
    if sheet_name:
        chosen = [item for item in matched if item[0] == sheet_name]
        if not chosen:
            raise SystemExit(f"打卡簿没有带夜班、加班的工作表：{sheet_name}")
    elif len(matched) == 1:
        chosen = matched
    elif not matched:
        raise SystemExit("打卡簿里没有已经算好的夜班、加班列")
    else:
        raise SystemExit("打卡簿里多张表都有夜班、加班，请用 --punch-sheet 指定：" + "、".join(item[0] for item in matched))
    _name, ws, headers = chosen[0]
    name_row, name_col = headers["姓名"]
    _night_row, night_col = headers["夜班"]
    _ot_row, ot_col = headers["加班"]
    start = max(name_row, headers["夜班"][0], headers["加班"][0]) + 1
    totals = {}
    for row in range(start, ws.max_row + 1):
        person = ws.cell(row, name_col).value
        if person is None or compact(person) == "":
            continue
        night = ws.cell(row, night_col).value
        overtime = ws.cell(row, ot_col).value
        if night is None or overtime is None:
            raise SystemExit(f"{person} 的夜班或加班还没算")
        totals[compact(person)] = (float(night), float(overtime))
    return totals


def save_workbook(wb, path):
    try:
        wb.save(path)
        return path
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_已填写{path.suffix}")
        wb.save(fallback)
        print(f"原文件被占用，已另存为 {fallback}")
        return fallback


def fill(pay_path, punch_path, sheet_name, punch_sheet, cap, dry_run):
    wb = load_workbook(pay_path)
    if sheet_name not in wb.sheetnames:
        raise SystemExit("没有这张月表：" + "、".join(wb.sheetnames))
    ws = wb[sheet_name]
    header_row = find_header_row(ws)
    columns = header_columns(ws, header_row)
    rows = employee_rows(ws, header_row, columns["姓名"])
    _coord, match = average_formula(ws)
    budget_cell, quota, _night_sum, _prior, _festival, constant, _ot_sum = match.groups()
    quota = int(quota)
    constant = float(constant)
    budget = numeric_expr(ws[budget_cell].value)
    totals = punch_totals(punch_path, punch_sheet)

    people = []
    prior_sum = 0.0
    festival_sum = 0.0
    for row in rows:
        name = str(ws.cell(row, columns["姓名"]).value)
        key = compact(name)
        if key not in totals:
            raise SystemExit(f"打卡表没有 {name}")
        raw_night, raw_ot = totals[key]
        rate = numeric_expr(ws.cell(row, columns["夜班标准"]).value)
        if rate != 5:
            raise SystemExit(f"{name} 的夜班标准是 {rate}，平均加班费公式按 5 元计算，请先确认")
        prior_sum += numeric_expr(ws.cell(row, columns["上月余额"]).value)
        festival_days = 0.0
        if "上报节日加班数" in columns:
            festival_days = numeric_expr(ws.cell(row, columns["上报节日加班数"]).value)
        salary = numeric_expr(ws.cell(row, columns["基本薪酬"]).value)
        festival_sum += salary / 21.75 * 3 * festival_days
        people.append((row, name, raw_night, raw_ot))

    raw_night_sum = sum(item[2] for item in people)
    raw_ot_sum = sum(item[3] for item in people)
    if raw_ot_sum == 0:
        raise SystemExit("打卡加班合计为 0，无法计算平均加班费")
    average = (budget + quota * 5 - 5 * raw_night_sum - prior_sum - festival_sum + constant) / raw_ot_sum
    if average <= 0:
        raise SystemExit(f"算出的平均加班费为 {average:.4f}，请先确认预算公式")

    written = []
    for row, name, raw_night, raw_ot in people:
        actual_night = min(raw_night, cap)
        excess = max(raw_night - cap, 0)
        actual_ot = raw_ot + excess * 5 / average
        written.append((name, raw_ot, raw_night, excess, actual_ot, actual_night))
        if not dry_run:
            ot_cell = ws.cell(row, columns["实际加班数"], actual_ot)
            night_cell = ws.cell(row, columns["实际夜班数"], actual_night)
            ot_cell.number_format = "0.00"
            night_cell.number_format = "0"

    night_written = sum(min(item[2], cap) for item in people)
    ot_written = sum(item[4] for item in written)
    check = (budget + (quota - night_written) * 5 - prior_sum - festival_sum + constant) / ot_written

    saved = pay_path if dry_run else save_workbook(wb, pay_path)
    print(f"工作表\t{ws.title}")
    print(f"文件\t{saved}")
    print(f"夜班上限\t{cap}")
    print(f"公式夜班额度\t{quota}")
    print(f"平均加班费\t{average:.2f}")
    print(f"验算平均加班费\t{check:.2f}")
    print("姓名\t打卡加班\t打卡夜班\t超出夜班\t实际加班数\t实际夜班数")
    for name, raw_ot, raw_night, excess, actual_ot, actual_night in written:
        print(f"{name}\t{raw_ot:g}\t{raw_night:g}\t{excess:g}\t{actual_ot:.2f}\t{actual_night:g}")


def main():
    configure_stdout()
    parser = argparse.ArgumentParser(description="填写实际加班数和实际夜班数")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--punch", type=Path, required=True)
    parser.add_argument("--sheet", required=True)
    parser.add_argument("--punch-sheet")
    parser.add_argument("--cap", type=float, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    fill(args.workbook, args.punch, args.sheet, args.punch_sheet, args.cap, args.dry_run)


if __name__ == "__main__":
    main()
