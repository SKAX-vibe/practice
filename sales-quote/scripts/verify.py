"""outbox/drafts/ 회신 초안과 report/견적처리.md 를 inbox/ · data/단가표.csv 원본과 대조해 PASS/FAIL 을 출력한다.

사용법: python scripts/verify.py
원본, 초안, 보고서는 읽기만 한다. 모두 일치하면 종료 코드 0, 불일치가 있으면 1.
품목은 단가표의 품목명과 정확히 같을 때만 단가를 적용한다(예: '스프링 와셔 M8' ≠ '와셔 M8').
요청 단위가 단가표 단위와 다르면(예: 박스) 수량을 알 수 없으므로 '확인 필요'다.
할인은 적용하지 않는다. 할인 요청이 있는 문의는 초안에 '할인'을 확인 필요로 남겨야 한다.
"""
import csv
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX = os.path.join(ROOT, "inbox")
PRICE_TABLE = os.path.join(ROOT, "data", "단가표.csv")
DRAFT_DIR = os.path.join(ROOT, "outbox", "drafts")
REPORT = os.path.join(ROOT, "report", "견적처리.md")

CHECK = "확인 필요"
REASON_NO_ITEM = "단가표에 없는 품목"
REASON_UNIT = "단위 불분명"


def load_prices():
    with open(PRICE_TABLE, encoding="utf-8-sig", newline="") as f:
        return {r["품목"].strip(): (int(r["단가"]), r["단위"].strip()) for r in csv.DictReader(f)}


def load_inquiries(prices):
    inquiries = []
    for path in sorted(glob.glob(os.path.join(INBOX, "*.txt"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        sender = re.search(r"^보낸 사람:\s*(.+)$", text, re.M).group(1).strip()
        received = re.search(r"^받은 날짜:\s*(\S+)", text, re.M).group(1)
        items = []
        for name, qty, unit in re.findall(r"^- (.+?)\s+([\d,]+)\s*([^\d\s,]+)\s*$", text, re.M):
            qty = int(qty.replace(",", ""))
            item = {"품목": name.strip(), "수량": qty, "단위": unit}
            if item["품목"] not in prices:
                item.update(단가=None, 금액=None, 사유=REASON_NO_ITEM)
            elif unit != prices[item["품목"]][1]:
                item.update(단가=None, 금액=None, 사유=REASON_UNIT)
            else:
                price = prices[item["품목"]][0]
                item.update(단가=price, 금액=price * qty, 사유="")
            items.append(item)
        inquiries.append({
            "파일": os.path.basename(path),
            "문의": os.path.splitext(os.path.basename(path))[0],
            "거래처": sender.split()[0],
            "날짜": received[5:],
            "품목": items,
            "합계": sum(i["금액"] or 0 for i in items),
            "할인요청": "할인" in text,
        })
    return inquiries


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


def price_cell(value):
    """단가·금액 칸의 비교값: 숫자 또는 '확인 필요'."""
    return CHECK if CHECK in value else to_int(value)


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
            print(f"       초안/보고서: {actual}")
            print(f"       기대값: {expected}")
        return ok


def check_draft(ck, inq):
    path = os.path.join(DRAFT_DIR, f"회신_{inq['거래처']}.md")
    label = f"{inq['문의']}({inq['거래처']})"
    if not ck.check(f"{label} 초안 존재", os.path.exists(path), True):
        return
    with open(path, encoding="utf-8") as f:
        text = f.read()
    ck.check(f"{label} 원문 파일 표기", inq["파일"] in text, True)
    rows = read_tables(text).get("2", [])
    items = [r for r in rows if len(r) >= 4 and r[0] != "합계"]
    ck.check(f"{label} 품목 목록", [r[0] for r in items], [i["품목"] for i in inq["품목"]])
    for row, item in zip(items, inq["품목"]):
        expected_price = item["단가"] if item["단가"] is not None else CHECK
        expected_amount = item["금액"] if item["금액"] is not None else CHECK
        ck.check(f"{label} '{item['품목']}' 수량/단가/금액",
                 (to_int(row[1]), price_cell(row[2]), price_cell(row[3])),
                 (item["수량"], expected_price, expected_amount))
    total = next((r for r in rows if r and r[0] == "합계"), None)
    ck.check(f"{label} 합계(확인 필요 제외, 할인 미적용)", to_int(total[3]) if total else None, inq["합계"])
    if inq["할인요청"]:
        ck.check(f"{label} 할인 요청을 '{CHECK}'로 표기",
                 bool(re.search(rf"할인.*{CHECK}|{CHECK}.*할인", text)), True)


def check_report(ck, inquiries):
    if not ck.check("보고서 존재", os.path.exists(REPORT), True):
        return
    with open(REPORT, encoding="utf-8") as f:
        text = f.read()
    tables = read_tables(text)

    rows = {r[0]: r for r in tables.get("2", []) if len(r) >= 6}
    ck.check("2장 문의 목록", sorted(k for k in rows if k != "합계"), [i["문의"] for i in inquiries])
    for inq in inquiries:
        row = rows.get(inq["문의"])
        actual = (row[1], to_int(row[3]), to_int(row[4]), to_int(row[5])) if row else None
        checks = sum(1 for i in inq["품목"] if i["단가"] is None)
        ck.check(f"2장 {inq['문의']} 거래처/품목 수/견적 금액/확인 필요",
                 actual, (inq["거래처"], len(inq["품목"]), inq["합계"], checks))
    total = rows.get("합계")
    ck.check("2장 합계 품목 수/견적 금액/확인 필요",
             (to_int(total[3]), to_int(total[4]), to_int(total[5])) if total else None,
             (sum(len(i["품목"]) for i in inquiries), sum(i["합계"] for i in inquiries),
              sum(1 for q in inquiries for i in q["품목"] if i["단가"] is None)))

    expected = sorted(
        (q["문의"], i["품목"], i["사유"]) for q in inquiries for i in q["품목"] if i["단가"] is None
    )
    actual = sorted((r[0], r[2], r[4]) for r in tables.get("3", []) if len(r) >= 5)
    ck.check("3장 확인 필요 품목(문의, 품목, 사유)", actual, expected)

    drafted = sum(os.path.exists(os.path.join(DRAFT_DIR, f"회신_{q['거래처']}.md")) for q in inquiries)
    ck.check("요약 처리 건수",
             bool(re.search(rf"문의 \*\*{len(inquiries)}건\*\* 중 회신 초안 \*\*{drafted}건\*\*", text)), True)
    ck.check("요약 확인 필요 품목 수",
             bool(re.search(rf"확인 필요 품목 \*\*{len(expected)}개\*\*", text)), True)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    prices = load_prices()
    inquiries = load_inquiries(prices)

    print(f"문의 {len(inquiries)}건 / 품목 {sum(len(i['품목']) for i in inquiries)}개")
    for inq in inquiries:
        checks = [i["품목"] for i in inq["품목"] if i["단가"] is None]
        print(f"  {inq['문의']} {inq['거래처']}: 합계 {inq['합계']:,}원, 확인 필요 {checks or '없음'}")
    print()

    ck = Checker()
    for inq in inquiries:
        check_draft(ck, inq)
    check_report(ck, inquiries)

    print()
    if ck.failures:
        print(f"결과: FAIL ({ck.failures}개 항목 불일치)")
        return 1
    print("결과: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
