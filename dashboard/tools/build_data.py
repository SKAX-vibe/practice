"""공개용 대시보드 데이터 생성.

각 트랙의 report/ 결과물을 읽어 집계 수치만 dashboard/data/dashboard.json 으로 쓴다.
원문 문장, 행 단위 내역(발주번호 · 사번 · 이름 · 품목), 단가, 확인 필요 항목의 내용은 넣지 않는다.

사용법 (저장소 최상위 폴더에서):
    python dashboard/tools/build_data.py            # dashboard/data/dashboard.json 생성
    python dashboard/tools/build_data.py --out X    # 다른 경로에 생성 (최신 여부 비교용)
"""

import argparse
import csv
import io
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "dashboard" / "data" / "dashboard.json"

# 대상 인원이 이 값보다 적은 부서는 개인 식별을 막기 위해 '기타 부서(합산)'로 묶는다.
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
            rows = [dict(zip(headers, (clean(c) for c in r))) for r in body]
            tables.append({"headers": headers, "rows": rows})
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
    return next(iter(row.values()), "") in ("합계",)


def count_drafts(track, pattern):
    return len(list((REPO / track / "outbox" / "drafts").glob(pattern)))


def verify_summary(track):
    src = read(f"{track}/report/검증결과.md")
    final = re.search(r"최종 결과:\s*(\S+)", src)
    run = re.search(r"실행일:\s*([\d-]+)", src)
    base = re.search(r"기준일:\s*([\d-]+)", src)
    checks = []
    for row in find_table(md_tables(src), "검증 대상", "방법", "결과")["rows"]:
        m = re.match(r"(PASS|FAIL)\s*(?:\((\d+)/(\d+)\))?", row["결과"])
        label = "자동 검증 스크립트" if "verify.py" in row["방법"] else row["방법"]
        item = {"method": label, "result": m.group(1) if m else row["결과"]}
        if m and m.group(2):
            item["passed"], item["total"] = int(m.group(2)), int(m.group(3))
        checks.append(item)
    return {
        "final": final.group(1) if final else "",
        "run_date": run.group(1) if run else "",
        "base_date": base.group(1) if base else "",
        "checks": checks,
    }


def won(n):
    return f"{n:,}원"


def signed_won(n):
    return ("+" if n > 0 else "−" if n < 0 else "") + f"{abs(n):,}원"


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


# ---------- 트랙별 집계 ----------

def track_a():
    key = "sales-quote"
    src = f"{key}/report/견적처리.md"
    main = find_table(md_tables(read(src)), "거래처", "품목 수", "견적 금액")
    rows = [r for r in main["rows"] if not is_total(r)]
    total = next(r for r in main["rows"] if is_total(r))
    amount = sum(to_num(r["견적 금액"]) for r in rows)
    assert amount == to_num(total["견적 금액"]), "견적 금액 합계 불일치"
    items = sum(to_num(r["품목 수"]) for r in rows)
    return {
        "id": "A", "key": key, "name": "영업", "desc": "견적 문의 회신",
        "sources": [src],
        "kpis": [
            {"label": "견적 문의", "value": f"{len(rows)}건", "sub": f"품목 {items}개"},
            {"label": "회신 초안", "value": f"{count_drafts(key, '회신_*.md')}건", "tone": "good"},
            {"label": "견적 금액 합계", "value": won(amount), "sub": "부가세 별도"},
            {"label": "확인 필요 품목", "value": f"{to_num(total['확인 필요'])}개", "tone": "warn"},
        ],
        "charts": [{
            "type": "bar", "title": "거래처별 견적 금액",
            "items": [{"label": r["거래처"], "value": to_num(r["견적 금액"]), "display": won(to_num(r["견적 금액"]))} for r in rows],
        }],
        "tables": [{
            "title": "거래처별 견적 집계",
            "headers": ["거래처", "품목 수", "견적 금액"],
            "align": ["left", "right", "right"],
            "rows": [[r["거래처"], f"{to_num(r['품목 수'])}개", won(to_num(r["견적 금액"]))] for r in rows],
            "total": ["합계", f"{items}개", won(amount)],
        }],
    }


def track_b():
    key = "hr-training"
    src = f"{key}/report/교육이수.md"
    tables = md_tables(read(src))
    main = find_table(tables, "과정", "부서", "대상", "이수", "이수율")
    missing = find_table(tables, "사번", "상태", "기한")
    check = find_table(tables, "구분", "사번", "내용")

    courses = list(dict.fromkeys(r["과정"] for r in main["rows"]))
    dept_rows = [r for r in main["rows"] if r["부서"] != "전체"]
    depts = list(dict.fromkeys(r["부서"] for r in dept_rows))
    size = {d: to_num(next(r for r in dept_rows if r["부서"] == d)["대상"]) for d in depts}
    shown = [d for d in depts if size[d] >= MIN_GROUP]
    merged = [d for d in depts if size[d] < MIN_GROUP]
    if merged and sum(size[d] for d in merged) < MIN_GROUP:
        raise ValueError("합산해도 소규모인 부서가 남습니다")
    other = f"기타 {len(merged)}개 부서"

    def agg(course, ds):
        rs = [r for r in dept_rows if r["과정"] == course and r["부서"] in ds]
        t, d, l = (sum(to_num(r[c]) for r in rs) for c in ("대상", "이수", "지연"))
        return {"대상": t, "이수": d, "미이수": t - d, "지연": l, "이수율": pct(d, t)}

    groups = [(d, [d]) for d in shown] + ([(other, merged)] if merged else [])
    overall = {c: agg(c, depts) for c in courses}
    for c in courses:  # 보고서의 '전체' 행과 같은지 확인
        row = next(r for r in main["rows"] if r["과정"] == c and r["부서"] == "전체")
        assert overall[c]["이수"] == to_num(row["이수"]) and overall[c]["대상"] == to_num(row["대상"]), f"{c} 합계 불일치"

    late = [r for r in missing["rows"] if r["상태"] == "지연"]
    kpis = [
        {"label": f"{c} 이수율", "value": f"{overall[c]['이수율']:.1f}%",
         "sub": f"이수 {overall[c]['이수']}명 / 대상 {overall[c]['대상']}명",
         **({"tone": "good"} if overall[c]["이수율"] >= 100 else {})}
        for c in courses
    ]
    kpis += [
        {"label": "지연 (연인원)", "value": f"{len(late)}명", "sub": f"실인원 {len({r['사번'] for r in late})}명 · 독려 초안 {count_drafts(key, '독려_*.md')}건", "tone": "warn"},
        {"label": "확인 필요 항목", "value": f"{len(check['rows'])}건", "sub": "담당자 판단 필요", "tone": "warn"},
    ]
    fmt_row = lambda c, label, a: [c, label, f"{a['대상']}명", f"{a['이수']}명", f"{a['미이수']}명", f"{a['이수율']:.1f}%", f"{a['지연']}명"]
    rows, total_rows = [], []
    for c in courses:
        rows += [fmt_row(c, label, agg(c, ds)) for label, ds in groups]
        total_rows.append(len(rows))
        rows.append(fmt_row(c, "전체", overall[c]))
    return {
        "id": "B", "key": key, "name": "인사", "desc": "교육 이수 · 독려",
        "sources": [src],
        "note": f"개인 식별 방지: 대상 {MIN_GROUP}명 미만 부서({', '.join(merged)})는 '{other}'로 합산해 표시합니다." if merged else "",
        "kpis": kpis,
        "charts": [{
            "type": "grouped", "title": "부서별 이수율", "series": courses, "max": 100,
            "ticks": ["0%", "25%", "50%", "75%", "100%"],
            "groups": [{"label": label, "values": [
                {"series": c, "value": agg(c, ds)["이수율"], "display": f"{agg(c, ds)['이수율']:.1f}%",
                 "tip": f"이수 {agg(c, ds)['이수']}명 / 대상 {agg(c, ds)['대상']}명"} for c in courses]}
                for label, ds in groups],
        }],
        "tables": [{
            "title": "과정 · 부서별 이수 현황",
            "headers": ["과정", "부서", "대상", "이수", "미이수", "이수율", "지연"],
            "align": ["left", "left", "right", "right", "right", "right", "right"],
            "rows": rows,
            "total_rows": total_rows,
        }],
    }


def track_c():
    key = "fin-invoice"
    src = f"{key}/report/대조.csv"
    rows = list(csv.DictReader(io.StringIO(read(src))))
    order = ["일치", "금액 차이", "계산서 없음"]
    unknown = {r["판정"] for r in rows} - set(order)
    if unknown:
        raise ValueError(f"알 수 없는 판정: {unknown}")
    n = lambda v: int(v) if v.strip() else 0
    by = {s: [r for r in rows if r["판정"] == s] for s in order}
    stat = {s: {"count": len(rs), "supply": sum(n(r["공급가액"]) for r in rs),
                "invoice": sum(n(r["계산서금액"]) for r in rs), "diff": sum(n(r["차액"]) for r in rs)}
            for s, rs in by.items()}
    tot = {k: sum(v[k] for v in stat.values()) for k in ("count", "supply", "invoice", "diff")}
    mismatch = stat["금액 차이"]["count"] + stat["계산서 없음"]["count"]
    return {
        "id": "C", "key": key, "name": "재무 · 구매", "desc": "발주 · 세금계산서 대조",
        "sources": [src],
        "kpis": [
            {"label": "발주", "value": f"{tot['count']}건", "sub": f"계산서 대응 {sum(1 for r in rows if r['계산서번호'])}건"},
            {"label": "일치", "value": f"{stat['일치']['count']}건", "tone": "good"},
            {"label": "불일치", "value": f"{mismatch}건", "sub": f"확인 요청 초안 {count_drafts(key, '확인요청_*.md')}건", "tone": "warn"},
            {"label": "차액 합계", "value": signed_won(tot["diff"]), "sub": "계산서 − 공급가액"},
        ],
        "charts": [{"type": "status", "title": "판정 구성",
                    "items": [{"name": s, "count": stat[s]["count"]} for s in order]}],
        "tables": [{
            "title": "판정별 집계",
            "headers": ["판정", "건수", "공급가액", "계산서 금액", "차액"],
            "align": ["left", "right", "right", "right", "right"],
            "status_col": 0,
            "rows": [[s, f"{v['count']}건", won(v["supply"]), won(v["invoice"]), signed_won(v["diff"])] for s, v in stat.items()],
            "total": ["합계", f"{tot['count']}건", won(tot["supply"]), won(tot["invoice"]), signed_won(tot["diff"])],
        }],
    }


def track_d():
    key = "ops-quality"
    src = f"{key}/report/품질주간.md"
    tables = md_tables(read(src))
    by_type = find_table(tables, "유형", "보고 건수", "불량 수량")
    by_line = find_table(tables, "라인", "보고 건수", "불량 수량")
    pending = find_table(tables, "날짜", "라인", "유형", "원인", "조치 상태")

    types = [r for r in by_type["rows"] if not is_total(r)]
    lines = [r for r in by_line["rows"] if not is_total(r)]
    total = next(r for r in by_type["rows"] if is_total(r))
    reports, qty = to_num(total["보고 건수"]), to_num(total["불량 수량"])
    status = {}
    for r in pending["rows"]:
        status[r["조치 상태"]] = status.get(r["조치 상태"], 0) + 1
    done = reports - len(pending["rows"])
    no_cause = sum(1 for r in pending["rows"] if r["원인"] == "원인 미기재")
    type_name = lambda s: re.sub(r"\s*\(.*\)$", "", s)  # 표기 메모는 빼고 유형명만
    bar = lambda r, label: {"label": label, "value": to_num(r["불량 수량"]), "display": f"{to_num(r['불량 수량'])}개",
                            "tip": f"{to_num(r['보고 건수'])}건 · {to_num(r['불량 수량'])}개"}
    return {
        "id": "D", "key": key, "name": "품질 · IT 운영", "desc": "불량 보고 주간 요약",
        "sources": [src],
        "kpis": [
            {"label": "불량 보고", "value": f"{reports}건"},
            {"label": "불량 수량", "value": f"{qty}개"},
            {"label": "미완료 조치", "value": f"{len(pending['rows'])}건", "sub": f"조치 완료 {done}건", "tone": "warn"},
            {"label": "원인 미기재", "value": f"{no_cause}건", "tone": "warn" if no_cause else "good"},
        ],
        "charts": [
            {"type": "bar", "title": "유형별 불량 수량", "items": [bar(r, type_name(r["유형"])) for r in types]},
            {"type": "bar", "title": "라인별 불량 수량", "items": [bar(r, f"{r['라인']}라인") for r in lines]},
        ],
        "tables": [{
            "title": "조치 상태별 집계",
            "headers": ["조치 상태", "보고 건수"],
            "align": ["left", "right"],
            "rows": [[s, f"{c}건"] for s, c in status.items()] + [["조치 완료", f"{done}건"]],
            "total": ["합계", f"{reports}건"],
        }],
    }


def build():
    tracks = []
    for fn in (track_a, track_b, track_c, track_d):
        t = fn()
        t["verify"] = verify_summary(t["key"])
        t["sources"].append(f"{t['key']}/report/검증결과.md")
        tracks.append(t)
    return {
        "title": "실습 결과 대시보드",
        "mode": "internal",
        "notice": "내부 실습 결과입니다. 각 트랙 report/ 결과물의 집계이며 외부 공개용이 아닙니다.",
        "min_group": MIN_GROUP,
        "tracks": tracks,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    out = Path(ap.parse_args().out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    out.write_bytes(text.encode("utf-8"))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
