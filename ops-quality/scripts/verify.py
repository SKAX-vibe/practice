"""report/품질주간.md 를 data/불량보고/ 원본과 대조해 PASS/FAIL 을 출력한다.

사용법: python scripts/verify.py
원본과 보고서는 읽기만 한다. 모두 일치하면 종료 코드 0, 불일치가 있으면 1.
유형은 TYPE_ALIASES 기준으로 정규화해 집계한다(D트랙: 긁힘 → 스크래치).
보고서의 유형 칸에 붙은 괄호 주석(예: "스크래치 (원본: 긁힘)")은 비교에서 제외한다.
"""
import glob
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "불량보고")
REPORT = os.path.join(ROOT, "report", "품질주간.md")

NO_CAUSE = "원인 미기재"
NO_ACTION = "조치 미기재"
DONE = "조치 완료"
TYPE_ALIASES = {"긁힘": "스크래치"}


def normalize_type(value):
    base = re.sub(r"\s*\(.*\)\s*$", "", value).strip()
    return TYPE_ALIASES.get(base, base)


def load_records():
    records = []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*.md"))):
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            fields = {k.strip(): v.strip() for k, v in re.findall(r"^- ([^:]+):[ \t]*(.*)$", f.read(), re.M)}
        mmdd = name[:4]
        records.append({
            "파일": name,
            "날짜": f"{mmdd[:2]}-{mmdd[2:]}",
            "라인": fields.get("라인", ""),
            "유형": normalize_type(fields.get("유형", "")),
            "수량": int(fields.get("수량") or 0),
            "원인": fields.get("원인") or NO_CAUSE,
            "조치": fields.get("조치") or NO_ACTION,
        })
    return records


def aggregate(records, key):
    result = defaultdict(lambda: [0, 0])
    for r in records:
        result[r[key]][0] += 1
        result[r[key]][1] += r["수량"]
    return {k: tuple(v) for k, v in result.items()}


def read_tables(text):
    """'## N. 제목' 섹션 번호 -> 표 본문 행(셀 리스트) 목록."""
    tables = {}
    for section in re.split(r"^## ", text, flags=re.M)[1:]:
        number = section.split(".", 1)[0].strip()
        rows = [
            [c.strip().strip("*").strip() for c in line.strip().strip("|").split("|")]
            for line in section.splitlines()
            if line.startswith("|")
        ]
        tables[number] = rows[2:]  # 머리글과 구분선 제외
    return tables


def to_int(cell):
    digits = re.sub(r"\D", "", cell)
    return int(digits) if digits else None


class Checker:
    def __init__(self):
        self.failures = 0

    def check(self, label, actual, expected):
        ok = actual == expected
        if ok:
            print(f"[PASS] {label}")
        else:
            self.failures += 1
            print(f"[FAIL] {label}")
            print(f"       보고서: {actual}")
            print(f"       기대값: {expected}")
        return ok


def check_summary_table(ck, tables, number, title, key, records):
    rows = tables.get(number)
    if rows is None:
        ck.check(f"{number}장 {title} 표 존재", "없음", "있음")
        return
    expected = aggregate(records, key)
    total = (len(records), sum(r["수량"] for r in records))
    found = {}
    duplicates = []
    for row in rows:
        if len(row) < 3:
            continue
        name = normalize_type(row[0]) if key == "유형" else row[0]
        if name in found:
            duplicates.append(row[0])
        found[name] = (to_int(row[1]), to_int(row[2]))
    ck.check(f"{number}장 {title} 정규화 후 중복 항목 없음", duplicates, [])
    ck.check(f"{number}장 {title} 항목 목록", sorted(k for k in found if k != "합계"), sorted(expected))
    for name in sorted(expected):
        c, q = expected[name]
        ck.check(f"{number}장 {title} '{name}' 건수/수량", found.get(name), (c, q))
    ck.check(f"{number}장 {title} 합계 건수/수량", found.get("합계"), total)
    ck.check(f"{number}장 {title} 건수 합 = 전체 보고 건수",
             sum(v[0] for k, v in found.items() if k != "합계" and v[0] is not None), len(records))


def check_open_actions(ck, tables, records):
    rows = tables.get("5")
    if rows is None:
        ck.check("5장 미완료 조치 표 존재", "없음", "있음")
        return
    expected = [
        [r["날짜"], r["라인"], r["유형"], f"{r['수량']}개", r["원인"], r["조치"]]
        for r in records if r["조치"] != DONE
    ]
    ck.check("5장 미완료 조치 행 수", len(rows), len(expected))
    for i, exp in enumerate(expected):
        actual = list(rows[i]) if i < len(rows) else None
        if actual and len(actual) > 2:
            actual[2] = normalize_type(actual[2])
        ck.check(f"5장 미완료 조치 {exp[0]} {exp[1]}라인", actual, exp)


def check_text(ck, text, records):
    total_count = len(records)
    total_qty = sum(r["수량"] for r in records)
    actions = aggregate(records, "조치")
    done = actions.get(DONE, (0, 0))[0]
    in_progress = actions.get("조치 중", (0, 0))[0]
    missing = actions.get(NO_ACTION, (0, 0))[0]
    expectations = [
        ("요약 전체 건수/수량", rf"보고 \*\*{total_count}건\*\*, 불량 수량 \*\*{total_qty}개\*\*"),
        ("요약 조치 완료 건수", rf"완료된 조치는 {done}건"),
        ("5장 미완료 내역",
         rf"미완료 {total_count - done}건\(조치 중 {in_progress}건, {NO_ACTION} {missing}건\)"),
    ]
    for label, pattern in expectations:
        ck.check(label, "일치" if re.search(pattern, text) else "불일치 또는 문구 없음", "일치")
    blank_cause = [r for r in records if r["원인"] == NO_CAUSE]
    ck.check(f"원인 없는 건 '{NO_CAUSE}' 표기", NO_CAUSE in text if blank_cause else True, True)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    records = load_records()
    if not os.path.exists(REPORT):
        print(f"[FAIL] 보고서 없음: {REPORT}")
        return 1
    with open(REPORT, encoding="utf-8") as f:
        text = f.read()
    tables = read_tables(text)

    print(f"원본 {len(records)}건 / 불량 수량 {sum(r['수량'] for r in records)}개")
    actions = aggregate(records, "조치")
    for name in ("조치 중", DONE, NO_ACTION):
        c, q = actions.get(name, (0, 0))
        print(f"  {name}: {c}건 / {q}개")
    print()

    ck = Checker()
    check_summary_table(ck, tables, "2", "유형별", "유형", records)
    check_summary_table(ck, tables, "3", "라인별", "라인", records)
    check_summary_table(ck, tables, "4", "원인별", "원인", records)
    check_open_actions(ck, tables, records)
    check_text(ck, text, records)

    print()
    if ck.failures:
        print(f"결과: FAIL ({ck.failures}개 항목 불일치)")
        return 1
    print("결과: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
