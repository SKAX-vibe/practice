"""report/대조.csv, report/대조요약.md, outbox/drafts/ 확인 요청 초안을 data/ 원본과 대조해 PASS/FAIL 을 출력한다.

사용법: python scripts/verify.py
원본, 대조표, 보고서, 초안은 읽기만 한다. 모두 일치하면 종료 코드 0, 불일치가 있으면 1.
- 세금계산서는 data/세금계산서*.csv 를 모두 읽는다(L11 세금계산서_추가.csv 대응).
- 발주 1건에 계산서가 여러 장이면 금액을 합산해 비교한다.
- 판정: 합계 = 공급가액이면 '일치', 다르면 '금액 차이', 계산서가 없으면 '계산서 없음'.
- 차액 = 계산서 금액 합계 - 공급가액. 부가세 포함 여부는 추정하지 않는다(1.1배여도 '금액 차이').
- 확인 요청 초안은 판정이 '일치'가 아닌 발주의 거래처마다 하나(outbox/drafts/확인요청_<거래처>.md).
"""
import csv
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
TABLE = os.path.join(ROOT, "report", "대조.csv")
REPORT = os.path.join(ROOT, "report", "대조요약.md")
DRAFT_DIR = os.path.join(ROOT, "outbox", "drafts")

MATCH, DIFF, MISSING = "일치", "금액 차이", "계산서 없음"
VERDICTS = (MATCH, DIFF, MISSING)


def read_csv(pattern):
    rows = []
    for path in sorted(glob.glob(os.path.join(DATA, pattern))):
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows.extend({k.strip(): v.strip() for k, v in r.items()} for r in csv.DictReader(f))
    return rows


def load():
    orders = read_csv("발주.csv")
    invoices = read_csv("세금계산서*.csv")
    po_ids = {o["발주번호"] for o in orders}
    by_po = {}
    for inv in invoices:
        by_po.setdefault(inv["발주번호"], []).append(inv)
    expected = []
    for o in orders:
        invs = by_po.get(o["발주번호"], [])
        supply = int(o["공급가액"])
        if invs:
            amount = sum(int(i["금액"]) for i in invs)
            verdict = MATCH if amount == supply else DIFF
            diff = amount - supply
        else:
            amount = diff = None
            verdict = MISSING
        expected.append({
            "발주번호": o["발주번호"], "거래처": o["거래처"], "공급가액": supply,
            "계산서번호": sorted(i["계산서번호"] for i in invs), "계산서금액": amount,
            "차액": diff, "판정": verdict,
            "거래처 불일치": sorted({i["거래처"] for i in invs if i["거래처"] != o["거래처"]}),
        })
    orphans = sorted(i["계산서번호"] for i in invoices if i["발주번호"] not in po_ids)
    return expected, orphans


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
    """'+275,000원', '-50000' 같은 칸을 정수로. 숫자가 없으면 None."""
    digits = re.sub(r"[^\d]", "", cell)
    if not digits:
        return None
    return -int(digits) if cell.strip().startswith(("-", "−")) else int(digits)


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
            print(f"       결과물: {actual}")
            print(f"       기대값: {expected}")
        return ok


def check_table(ck, expected):
    if not ck.check("대조표 존재", os.path.exists(TABLE), True):
        return
    with open(TABLE, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    ck.check("대조표 행 수 = 발주 건수", len(rows), len(expected))
    ck.check("판정 값은 일치 · 금액 차이 · 계산서 없음만", sorted({r.get("판정", "") for r in rows} - set(VERDICTS)), [])
    found = {r.get("발주번호", ""): r for r in rows}
    for e in expected:
        r = found.get(e["발주번호"])
        actual = None
        if r:
            actual = (sorted(x for x in re.split(r"[;,\s]+", r.get("계산서번호", "")) if x),
                      to_int(r.get("계산서금액", "")), to_int(r.get("차액", "")), r.get("판정"))
        ck.check(f"대조표 {e['발주번호']} 계산서번호/계산서금액/차액/판정", actual,
                 (e["계산서번호"], e["계산서금액"], e["차액"], e["판정"]))


def check_report(ck, expected, orphans):
    if not ck.check("요약 보고서 존재", os.path.exists(REPORT), True):
        return
    with open(REPORT, encoding="utf-8") as f:
        text = f.read()
    tables = read_tables(text)

    rows = {r[0]: r for r in tables.get("2", []) if len(r) >= 5}
    for v in VERDICTS + ("합계",):
        group = [e for e in expected if v in (e["판정"], "합계")]
        exp = (len(group), sum(e["공급가액"] for e in group),
               sum(e["계산서금액"] or 0 for e in group), sum(e["차액"] or 0 for e in group))
        row = rows.get(v)
        ck.check(f"2장 {v} 건수/공급가액/계산서 금액/차액",
                 tuple(to_int(c) for c in row[1:5]) if row else None, exp)

    diffs = [e for e in expected if e["판정"] != MATCH]
    actual = sorted((r[0], r[5]) for r in tables.get("3", []) if len(r) >= 6)
    ck.check("3장 차이 목록(발주번호, 판정)", actual, sorted((e["발주번호"], e["판정"]) for e in diffs))

    counts = {v: sum(e["판정"] == v for e in expected) for v in VERDICTS}
    net = sum(e["차액"] or 0 for e in expected)
    absolute = sum(abs(e["차액"] or 0) for e in expected)
    ck.check("요약 판정별 건수", bool(re.search(
        rf"발주 \*\*{len(expected)}건\*\*: 일치 \*\*{counts[MATCH]}건\*\* · 금액 차이 \*\*{counts[DIFF]}건\*\* · "
        rf"계산서 없음 \*\*{counts[MISSING]}건\*\*", text)), True)
    ck.check("요약 차액 합계", bool(re.search(
        rf"차액 합계\(계산서−발주\) \*\*{re.escape(f'{net:+,}' if net else '0')}원\*\*\(절대값 {absolute:,}원\)", text)),
        True)
    ck.check("발주에 없는 계산서 표기", [o for o in orphans if o not in text], [])


def check_drafts(ck, expected):
    targets = {}
    for e in expected:
        if e["판정"] != MATCH:
            targets.setdefault(e["거래처"], []).append(e)
    files = sorted(re.match(r"확인요청_(.+)\.md$", os.path.basename(p)).group(1)
                   for p in glob.glob(os.path.join(DRAFT_DIR, "확인요청_*.md")))
    ck.check("확인 요청 초안 대상 = 불일치 발주의 거래처", files, sorted(targets))
    for vendor, items in sorted(targets.items()):
        path = os.path.join(DRAFT_DIR, f"확인요청_{vendor}.md")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            rows = read_tables(f.read()).get("2", [])
        ck.check(f"확인요청_{vendor} 발주번호/차액/판정",
                 sorted((r[0], to_int(r[4]), r[5]) for r in rows if len(r) >= 6),
                 sorted((e["발주번호"], e["차액"], e["판정"]) for e in items))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    expected, orphans = load()

    print(f"발주 {len(expected)}건")
    for v in VERDICTS:
        print(f"  {v}: {[e['발주번호'] for e in expected if e['판정'] == v]}")
    print(f"  차액 합계: {sum(e['차액'] or 0 for e in expected):+,}원 / 발주에 없는 계산서: {orphans or '없음'}")
    for e in expected:
        if e["거래처 불일치"]:
            print(f"  거래처 불일치: {e['발주번호']} {e['거래처']} vs {e['거래처 불일치']}")
    print()

    ck = Checker()
    check_table(ck, expected)
    check_report(ck, expected, orphans)
    check_drafts(ck, expected)

    print()
    if ck.failures:
        print(f"결과: FAIL ({ck.failures}개 항목 불일치)")
        return 1
    print("결과: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
