"""data/단가표.csv 에서 품목명 · 단위를 조회해 단가 적용 여부를 판정한다.

사용법 (sales-quote 폴더에서):
    python tools/price_lookup.py "<품목명>" <단위>
    예) python tools/price_lookup.py "볼트 M8" 개

출력 (JSON 한 줄):
    {"품목": ..., "요청 단위": ..., "일치": true|false, "단가": 숫자|null, "단위": 단가표 단위|null, "확인 필요 사유": ""|사유}

판정 (CLAUDE.md 판단 기준과 같음, scripts/verify.py 와 같은 비교 방식):
- 품목명이 단가표와 정확히 같고 단위도 같을 때만 단가를 돌려준다.
- 단가표에 없는 품목 → 확인 필요 사유 "단가표에 없는 품목"
- 품목은 있으나 단위가 다름 → 확인 필요 사유 "단위 불분명" (단위 환산 · 금액은 추정하지 않음)
단가표는 읽기만 한다.

종료 코드: 0 = 단가 적용, 1 = 확인 필요, 2 = 사용법 · 단가표 오류
"""
import csv
import json
import sys
from pathlib import Path

PRICE_TABLE = Path(__file__).resolve().parents[1] / "data" / "단가표.csv"

REASON_NO_ITEM = "단가표에 없는 품목"
REASON_UNIT = "단위 불분명"


def load_prices(path=PRICE_TABLE):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["품목"].strip(): (int(r["단가"]), r["단위"].strip()) for r in csv.DictReader(f)}


def lookup(name, unit, prices):
    name, unit = name.strip(), unit.strip()
    result = {"품목": name, "요청 단위": unit, "일치": False, "단가": None, "단위": None, "확인 필요 사유": ""}
    if name not in prices:
        result["확인 필요 사유"] = REASON_NO_ITEM
        return result
    price, table_unit = prices[name]
    result["단위"] = table_unit
    if unit != table_unit:
        result["확인 필요 사유"] = REASON_UNIT
        return result
    result.update({"일치": True, "단가": price})
    return result


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if len(argv) != 2 or not argv[0].strip() or not argv[1].strip():
        print('사용법: python tools/price_lookup.py "<품목명>" <단위>', file=sys.stderr)
        return 2
    try:
        prices = load_prices()
    except (OSError, KeyError, ValueError) as e:
        print(f"단가표를 읽을 수 없습니다: {e}", file=sys.stderr)
        return 2
    result = lookup(argv[0], argv[1], prices)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["일치"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
