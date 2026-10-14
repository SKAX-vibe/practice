"""내부용 대시보드 데이터 생성 (구조 v2).

각 트랙의 report/ 결과물을 읽어 집계 수치만 dashboard/data/dashboard.json 으로 쓴다.
원문 문장, 행 단위 내역(발주번호 · 사번 · 이름 · 품목), 단가, 확인 필요 항목의 내용은 넣지 않는다.
모든 수치는 {value, unit} 로 단위를 함께 적는다 (건 · 명 · 개 · 원 · % · 항목).

사용법 (저장소 최상위 폴더에서):
    python dashboard/tools/build_data.py            # dashboard/data/dashboard.json 생성
    python dashboard/tools/build_data.py --out X    # 다른 경로에 생성 (최신 여부 비교용)
"""

import argparse
import sys
import csv
import io
import json
import re
from pathlib import Path

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
from components import collect as collect_components  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "dashboard" / "data" / "dashboard.json"

# 대상 인원이 이 값보다 적은 부서는 개인 식별을 막기 위해 '기타 N개 부서'로 묶는다.
MIN_GROUP = 3


# ---------- 읽기 ----------

def read(rel):
    return (REPO / rel).read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def clean(cell):
    return cell.replace("**", "").replace("`", "").strip()


def to_num(cell):
    s = clean(cell).replace("−", "-").replace("–", "-")
    s = re.sub(r"[^\d.\-]", "", s)
    if s in ("", "-"):
        raise ValueError(f"숫자가 아닙니다: {cell!r}")
    return float(s) if "." in s else int(s)


def md_tables(src):
    """문서 안의 표를 [{'headers': [...], 'rows': [dict, ...]}] 로 돌려준다."""
    tables, buf = [], []

    def flush():
        if len(buf) >= 2:
            split = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
            headers = [clean(h) for h in split(buf[0])]
            body = [split(r) for r in buf[1:] if not re.fullmatch(r"[\s|:\-]+", r)]
            tables.append({"headers": headers, "rows": [dict(zip(headers, (clean(c) for c in r))) for r in body]})
        buf.clear()

    for line in src.split("\n"):
        if line.strip().startswith("|"):
            buf.append(line)
        else:
            flush()
    flush()
    return tables


def find_table(tables, *cols):
    for t in tables:
        if all(c in t["headers"] for c in cols):
            return t
    raise ValueError(f"표를 찾지 못했습니다: {cols}")


def is_total(row):
    return next(iter(row.values()), "") == "합계"


def body_rows(table):
    return [r for r in table["rows"] if not is_total(r)]


def total_row(table):
    return next(r for r in table["rows"] if is_total(r))


def source_count(src, filename, unit):
    """보고서 '출처' 줄의 `파일명` N건/명 값을 읽는다."""
    m = re.search(rf"{re.escape(filename)}`\s*(\d+){unit}", src)
    if not m:
        raise ValueError(f"출처 줄에서 {filename} {unit} 를 찾지 못했습니다")
    return int(m.group(1))


def section_list_count(src, heading_prefix):
    """'## N. 제목' 절 안의 번호 목록 개수."""
    m = re.search(rf"^## {re.escape(heading_prefix)}.*?$(.*?)(?=^## |\Z)", src, re.M | re.S)
    if not m:
        raise ValueError(f"절을 찾지 못했습니다: {heading_prefix}")
    return len(re.findall(r"^\d+\. ", m.group(1), re.M))


def count_drafts(track, pattern):
    return len(list((REPO / track / "outbox" / "drafts").glob(pattern)))


def q(value, unit, label=None):
    item = {"value": value, "unit": unit}
    if label:
        item = {"label": label, **item}
    return item


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


def verify_summary(track):
    src = read(f"{track}/report/검증결과.md")
    final = re.search(r"최종 결과:\s*(\S+)", src)
    run = re.search(r"실행일:\s*([\d-]+)", src)
    base = re.search(r"기준일:\s*([\d-]+)", src)
    out = {"final": final.group(1) if final else "", "run_date": run.group(1) if run else "",
           "base_date": base.group(1) if base else ""}
    for row in find_table(md_tables(src), "검증 대상", "방법", "결과")["rows"]:
        m = re.match(r"(PASS|FAIL)\s*(?:\((\d+)/(\d+)\))?", row["결과"])
        if "verify.py" in row["방법"] and m:
            out["script"] = {"result": m.group(1), "passed": q(int(m.group(2)), "항목"), "total": q(int(m.group(3)), "항목")}
        elif row["방법"] == "사실성 검토" and m:
            out["factual"] = m.group(1)
    return out


# ---------- 트랙별 집계 ----------

def track_a():
    key = "sales-quote"
    src_path = f"{key}/report/견적처리.md"
    src = read(src_path)
    main = find_table(md_tables(src), "거래처", "품목 수", "견적 금액", "확인 필요")
    rows, total = body_rows(main), total_row(main)
    inquiries = [{
        "name": r["거래처"],
        "items": q(to_num(r["품목 수"]), "개"),
        "amount": q(to_num(r["견적 금액"]), "원"),
        "review": q(to_num(r["확인 필요"]), "개"),
        "draft": bool(r.get("초안")),
    } for r in rows]
    amount = sum(i["amount"]["value"] for i in inquiries)
    items = sum(i["items"]["value"] for i in inquiries)
    review = sum(i["review"]["value"] for i in inquiries)
    assert (amount, items, review) == (to_num(total["견적 금액"]), to_num(total["품목 수"]), to_num(total["확인 필요"])), "A 합계 불일치"
    drafts = count_drafts(key, "회신_*.md")
    assert drafts == sum(i["draft"] for i in inquiries), "A 초안 수 불일치"
    other = section_list_count(src, "4.")
    return {
        "id": "A", "key": key, "name": "영업", "task": "견적 문의 회신",
        "question": "바로 보낼 수 있는 회신과, 사람이 확인할 항목은 무엇인가",
        "sources": [src_path],
        "flow": {
            "input": [q(len(inquiries), "건", "견적 문의")],
            "output": [q(drafts, "건", "회신 초안")],
            "review": [q(review, "개", "확인 필요 품목"), q(other, "건", "품목 외 확인 사항")],
        },
        "view": "quotes",
        "detail": {
            "amount_total": q(amount, "원"),
            "amount_note": "부가세 별도 · 확인 필요 품목 제외",
            "items_total": q(items, "개"),
            "items_quoted": q(items - review, "개"),
            "items_review": q(review, "개"),
            "other_review": q(other, "건"),
            "inquiries": inquiries,
        },
    }


def track_b():
    key = "hr-training"
    src_path = f"{key}/report/교육이수.md"
    src = read(src_path)
    tables = md_tables(src)
    main = find_table(tables, "과정", "부서", "대상", "이수", "이수율")
    late_table = find_table(tables, "사번", "상태", "기한")
    check = find_table(tables, "구분", "사번", "내용")

    courses = list(dict.fromkeys(r["과정"] for r in main["rows"]))
    dept_rows = [r for r in main["rows"] if r["부서"] != "전체"]
    depts = list(dict.fromkeys(r["부서"] for r in dept_rows))
    size = {d: to_num(next(r for r in dept_rows if r["부서"] == d)["대상"]) for d in depts}
    merged = [d for d in depts if size[d] < MIN_GROUP]
    if merged and sum(size[d] for d in merged) < MIN_GROUP:
        raise ValueError("합산해도 소규모인 부서가 남습니다")
    other = f"기타 {len(merged)}개 부서"
    groups = [(d, [d]) for d in depts if d not in merged] + ([(other, merged)] if merged else [])

    def agg(course, ds):
        rs = [r for r in dept_rows if r["과정"] == course and r["부서"] in ds]
        target, done = (sum(to_num(r[c]) for r in rs) for c in ("대상", "이수"))
        return {"course": course, "target": q(target, "명"), "done": q(done, "명"), "rate": q(pct(done, target), "%")}

    overall = []
    for c in courses:
        a = agg(c, depts)
        row = next(r for r in main["rows"] if r["과정"] == c and r["부서"] == "전체")
        assert (a["target"]["value"], a["done"]["value"]) == (to_num(row["대상"]), to_num(row["이수"])), f"B {c} 합계 불일치"
        overall.append(a)

    late = [r for r in late_table["rows"] if r["상태"] == "지연"]
    late_people = len({r["사번"] for r in late})
    drafts = count_drafts(key, "독려_*.md")
    roster = source_count(src, "직원명단.csv", "명")
    records = source_count(src, "수료기록.csv", "건")
    assert roster == overall[0]["target"]["value"], "B 명단 인원 불일치"
    return {
        "id": "B", "key": key, "name": "인사", "task": "교육 이수 · 독려",
        "question": "과정별 이수는 어느 정도이고, 지연자 독려는 빠짐없이 준비됐는가",
        "sources": [src_path],
        "flow": {
            "input": [q(roster, "명", "직원 명단"), q(records, "건", "수료 기록")],
            "output": [q(drafts, "건", "독려 초안")],
            "review": [q(len(check["rows"]), "건", "확인 필요 항목")],
        },
        "view": "training",
        "detail": {
            "courses": overall,
            "groups": [{"name": label, "size": q(sum(size[d] for d in ds), "명"), "cells": [agg(c, ds) for c in courses]}
                       for label, ds in groups],
            "merge_note": f"대상 {MIN_GROUP}명 미만 부서({', '.join(merged)})는 개인 식별 방지를 위해 '{other}'로 합산" if merged else "",
            "late_count": q(len(late), "건", "지연 (과정 기준)"),
            "late_people": q(late_people, "명", "지연 실인원"),
            "draft_count": q(drafts, "건", "독려 초안 (1인 1건)"),
        },
    }


def track_c():
    key = "fin-invoice"
    src_path = f"{key}/report/대조.csv"
    summary_path = f"{key}/report/대조요약.md"
    rows = list(csv.DictReader(io.StringIO(read(src_path))))
    order = ["일치", "금액 차이", "계산서 없음"]
    unknown = {r["판정"] for r in rows} - set(order)
    if unknown:
        raise ValueError(f"알 수 없는 판정: {unknown}")
    n = lambda v: int(v) if v.strip() else 0
    verdicts = []
    for s in order:
        rs = [r for r in rows if r["판정"] == s]
        verdicts.append({"name": s, "count": q(len(rs), "건"), "vendors": q(len({r["거래처"] for r in rs}), "곳"),
                         "supply": q(sum(n(r["공급가액"]) for r in rs), "원"),
                         "invoice": q(sum(n(r["계산서금액"]) for r in rs), "원"),
                         "diff": q(sum(n(r["차액"]) for r in rs), "원")})
    total = {k: q(sum(v[k]["value"] for v in verdicts), "원") for k in ("supply", "invoice", "diff")}
    mismatch_rows = [r for r in rows if r["판정"] != "일치"]
    drafts = count_drafts(key, "확인요청_*.md")
    invoices = source_count(read(summary_path), "세금계산서.csv", "건")
    return {
        "id": "C", "key": key, "name": "재무 · 구매", "task": "발주 · 세금계산서 대조",
        "question": "자동 대조로 얼마나 맞았고, 어디가 어긋났는가",
        "sources": [src_path, summary_path],
        "flow": {
            "input": [q(len(rows), "건", "발주"), q(invoices, "건", "세금계산서")],
            "output": [q(len(rows), "건", "자동 판정"), q(drafts, "건", "확인 요청 초안")],
            "review": [q(len(mismatch_rows), "건", "불일치")],
        },
        "view": "reconcile",
        "detail": {
            "verdicts": verdicts,
            "total": total,
            "mismatch": q(len(mismatch_rows), "건", "불일치 발주"),
            "mismatch_vendors": q(len({r["거래처"] for r in mismatch_rows}), "곳", "불일치 거래처"),
            "draft_count": q(drafts, "건", "확인 요청 초안 (거래처별)"),
        },
    }


def track_d():
    key = "ops-quality"
    src_path = f"{key}/report/품질주간.md"
    action_path = f"{key}/report/조치요청초안.md"
    tables = md_tables(read(src_path))
    by_type = find_table(tables, "유형", "보고 건수", "불량 수량")
    by_line = find_table(tables, "라인", "보고 건수", "불량 수량")
    pending = find_table(tables, "날짜", "라인", "유형", "원인", "조치 상태")
    total = total_row(by_type)
    reports, qty = to_num(total["보고 건수"]), to_num(total["불량 수량"])

    status = {}
    for r in pending["rows"]:
        status[r["조치 상태"]] = status.get(r["조치 상태"], 0) + 1
    done = reports - len(pending["rows"])
    no_cause = sum(1 for r in pending["rows"] if r["원인"] == "원인 미기재")

    action = read(action_path)
    basis = re.search(r"\*\*순위 기준:\*\*\s*(.+)", action).group(1)
    prio = find_table(md_tables(action), "순위", "구분", "보고 건수", "불량 수량")
    prio_groups = [{"name": r["구분"], "reports": q(to_num(r["보고 건수"]), "건"), "qty": q(to_num(r["불량 수량"]), "개")}
                   for r in body_rows(prio)]
    assert sum(g["reports"]["value"] for g in prio_groups) == reports, "D 정렬 그룹 합계 불일치"
    messages = len(re.findall(r"^### 메시지 \d+", action, re.M))

    # 보고 건별 내역(2-2): 날짜 · 라인 · 유형 · 수량. 개수와 수량만 집계한다 (원인 등 내용은 넣지 않음).
    per_report = find_table(md_tables(action), "순위", "날짜", "라인", "유형", "수량")["rows"]
    type_of = lambda r: re.sub(r"\s*\(.*\)$", "", r["유형"])
    assert len(per_report) == reports and sum(to_num(r["수량"]) for r in per_report) == qty, "D 보고 건별 내역 합계 불일치"
    dates = sorted({r["날짜"] for r in per_report})
    cells = {}
    for r in per_report:
        c = cells.setdefault((f"{r['라인']}라인", type_of(r)), [0, 0])
        c[0] += 1
        c[1] += to_num(r["수량"])
    matrix = [{"line": l, "type": t, "reports": q(n, "건"), "qty": q(v, "개")} for (l, t), (n, v) in sorted(cells.items())]
    for key_, rows_, name_ in (("line", by_line, lambda r: f"{r['라인']}라인"), ("type", by_type, type_of)):
        for r in body_rows(rows_):
            assert sum(m["qty"]["value"] for m in matrix if m[key_] == name_(r)) == to_num(r["불량 수량"]), f"D 행렬 {key_} 합계 불일치"
    daily = [{"date": d, "reports": q(sum(1 for r in per_report if r["날짜"] == d), "건"),
              "qty": q(sum(to_num(r["수량"]) for r in per_report if r["날짜"] == d), "개")} for d in dates]

    dist = lambda t, fmt: [{"name": fmt(r), "reports": q(to_num(r["보고 건수"]), "건"), "qty": q(to_num(r["불량 수량"]), "개")}
                           for r in body_rows(t)]
    return {
        "id": "D", "key": key, "name": "품질 · IT 운영", "task": "불량 보고 주간 요약",
        "question": "어떤 보고부터 확인해야 하고, 조치는 얼마나 진행됐는가",
        "sources": [src_path, action_path],
        "flow": {
            "input": [q(reports, "건", "불량 보고"), q(qty, "개", "불량 수량")],
            "output": [q(messages, "건", "조치 요청 메시지 (라인별)")],
            "review": [q(len(pending["rows"]), "건", "미완료 조치"), q(no_cause, "건", "원인 미기재")],
        },
        "view": "quality",
        "detail": {
            "order_basis": [s.strip() for s in basis.split(">")],
            "order_groups": prio_groups,
            "status": [{"name": s, "reports": q(c, "건")} for s, c in status.items()] + [{"name": "조치 완료", "reports": q(done, "건")}],
            "done": q(done, "건"), "reports": q(reports, "건"), "qty": q(qty, "개"),
            "types": dist(by_type, lambda r: re.sub(r"\s*\(.*\)$", "", r["유형"])),
            "lines": dist(by_line, lambda r: f"{r['라인']}라인"),
            "daily": daily,
            "matrix": matrix,
        },
    }


def build():
    tracks = []
    components = collect_components(REPO)
    for fn in (track_a, track_b, track_c, track_d):
        t = fn()
        t["verify"] = verify_summary(t["key"])
        t["sources"].append(f"{t['key']}/report/검증결과.md")
        t["components"] = components[t["key"]]
        tracks.append(t)
    return {
        "schema": 2,
        "title": "실습 결과 대시보드",
        "mode": "internal",
        "notice": "내부 확인용 · 각 트랙 report/ 결과물의 집계이며 외부 공개용이 아닙니다.",
        "min_group": MIN_GROUP,
        "tracks": tracks,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    out = Path(ap.parse_args().out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
