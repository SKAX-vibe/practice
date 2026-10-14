"""공개용 데모 데이터 생성 (구조 v2).

GitHub Pages에는 실제 실습 결과 대신 이 데모 데이터를 올린다.
아래 값은 화면 구성을 보여주기 위한 가상의 예시이며 저장소의 업무 파일을 읽지 않는다.
거래처 · 부서 · 과정 · 유형 명칭도 실제 자료와 겹치지 않는 예시 명칭만 쓴다.
검증 결과는 수치 없이 '예시'로만 표시한다 (final: DEMO).
구조는 build_data.py 가 만드는 data/dashboard.json 과 같다.
트랙별 '자동화 구성 요소'(components)는 데모 값이 아니라 저장소에 실제로 있는 커맨드 · Skill · 도구 · 기억 파일 목록이다
(tools/components.py, 파일 존재 여부만 확인하며 업무 자료는 읽지 않음).

사용법 (저장소 최상위 폴더에서):
    python dashboard/tools/build_demo.py            # dashboard/data/demo.json 생성
    python dashboard/tools/build_demo.py --out X    # 다른 경로에 생성 (최신 여부 비교용)
"""

import argparse
import sys
import json
from pathlib import Path

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
from components import collect as collect_components  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "dashboard" / "data" / "demo.json"


def q(value, unit, label=None):
    item = {"value": value, "unit": unit}
    return {"label": label, **item} if label else item


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


# ---------- 트랙별 예시 값 ----------

def track_a():
    # (거래처, 품목 수, 견적 금액, 확인 필요 품목 수)
    quotes = [("샘플거래처 가", 4, 152000, 1), ("샘플거래처 나", 3, 98500, 0),
              ("샘플거래처 다", 2, 64000, 1), ("샘플거래처 라", 2, 41500, 0)]
    items = sum(x[1] for x in quotes)
    review = sum(x[3] for x in quotes)
    amount = sum(x[2] for x in quotes)
    other = 1
    return {
        "id": "A", "key": "sales-quote", "name": "영업", "task": "견적 문의 회신",
        "question": "바로 보낼 수 있는 회신과, 사람이 확인할 항목은 무엇인가",
        "flow": {
            "input": [q(len(quotes), "건", "견적 문의")],
            "output": [q(len(quotes), "건", "회신 초안")],
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
            "inquiries": [{"name": n, "items": q(i, "개"), "amount": q(a, "원"), "review": q(r, "개"), "draft": True}
                          for n, i, a, r in quotes],
        },
    }


def track_b():
    courses = ["필수교육 A", "필수교육 B"]
    # (부서, 대상, 과정별 이수)
    depts = [("부서 1", 9, (8, 7)), ("부서 2", 7, (6, 5)), ("부서 3", 8, (7, 5)), ("부서 4", 7, (6, 4))]
    total = sum(d[1] for d in depts)
    cell = lambda c, target, done: {"course": c, "target": q(target, "명"), "done": q(done, "명"), "rate": q(pct(done, target), "%")}
    overall = [cell(c, total, sum(d[2][i] for d in depts)) for i, c in enumerate(courses)]
    late = sum(total - o["done"]["value"] for o in overall)
    late_people = 11
    return {
        "id": "B", "key": "hr-training", "name": "인사", "task": "교육 이수 · 독려",
        "question": "과정별 이수는 어느 정도이고, 지연자 독려는 빠짐없이 준비됐는가",
        "flow": {
            "input": [q(total, "명", "직원 명단"), q(sum(o["done"]["value"] for o in overall), "건", "수료 기록")],
            "output": [q(late_people, "건", "독려 초안")],
            "review": [q(3, "건", "확인 필요 항목")],
        },
        "view": "training",
        "detail": {
            "courses": overall,
            "groups": [{"name": n, "size": q(s, "명"), "cells": [cell(c, s, comp[i]) for i, c in enumerate(courses)]}
                       for n, s, comp in depts],
            "merge_note": "",
            "late_count": q(late, "건", "지연 (과정 기준)"),
            "late_people": q(late_people, "명", "지연 실인원"),
            "draft_count": q(late_people, "건", "독려 초안 (1인 1건)"),
        },
    }


def track_c():
    # 판정별 (건수, 공급가액, 계산서 금액)
    # 판정별 (건수, 거래처 수, 공급가액, 계산서 금액)
    stat = {"일치": (11, 6, 9600000, 9600000), "금액 차이": (3, 3, 3200000, 3080000), "계산서 없음": (1, 1, 700000, 0)}
    verdicts = [{"name": s, "count": q(c, "건"), "vendors": q(v, "곳"), "supply": q(sp, "원"), "invoice": q(iv, "원"),
                 "diff": q(iv - sp if s != "계산서 없음" else 0, "원")} for s, (c, v, sp, iv) in stat.items()]
    total = {k: q(sum(v[k]["value"] for v in verdicts), "원") for k in ("supply", "invoice", "diff")}
    po = sum(v["count"]["value"] for v in verdicts)
    mismatch = po - stat["일치"][0]
    mismatch_vendors = stat["금액 차이"][1] + stat["계산서 없음"][1]
    return {
        "id": "C", "key": "fin-invoice", "name": "재무 · 구매", "task": "발주 · 세금계산서 대조",
        "question": "자동 대조로 얼마나 맞았고, 어디가 어긋났는가",
        "flow": {
            "input": [q(po, "건", "발주"), q(po - stat["계산서 없음"][0], "건", "세금계산서")],
            "output": [q(po, "건", "자동 판정"), q(4, "건", "확인 요청 초안")],
            "review": [q(mismatch, "건", "불일치")],
        },
        "view": "reconcile",
        "detail": {
            "verdicts": verdicts,
            "total": total,
            "mismatch": q(mismatch, "건", "불일치 발주"),
            "mismatch_vendors": q(mismatch_vendors, "곳", "불일치 거래처"),
            "draft_count": q(4, "건", "확인 요청 초안 (거래처별)"),
        },
    }


def track_d():
    # 라인 × 유형 칸 (라인, 유형, 보고 건수, 불량 수량) → 유형별 · 라인별 합계는 여기서 계산
    cells = [("가라인", "이물 혼입", 2, 15), ("가라인", "도장 불량", 1, 7),
             ("나라인", "치수 불량", 2, 11), ("나라인", "이물 혼입", 1, 5),
             ("다라인", "이물 혼입", 1, 4), ("다라인", "도장 불량", 1, 11)]
    total_of = lambda idx, name: (sum(c[2] for c in cells if c[idx] == name), sum(c[3] for c in cells if c[idx] == name))
    types = [(t, *total_of(1, t)) for t in ("이물 혼입", "치수 불량", "도장 불량")]
    lines = [(l, *total_of(0, l)) for l in ("가라인", "나라인", "다라인")]
    daily = [("07-06", 2, 14), ("07-07", 1, 6), ("07-08", 2, 11), ("07-09", 1, 8), ("07-10", 2, 14)]
    status = [("조치 중", 4), ("조치 미기재", 1), ("조치 완료", 3)]
    groups = [("기록 누락", 2, 15), ("반복 원인", 3, 21), ("반복 유형", 3, 17)]
    reports = sum(t[1] for t in types)
    qty = sum(t[2] for t in types)
    assert reports == sum(d[1] for d in daily) and qty == sum(d[2] for d in daily)
    assert reports == sum(x[1] for x in lines) == sum(x[1] for x in status) == sum(g[1] for g in groups)
    assert qty == sum(x[2] for x in lines) == sum(g[2] for g in groups)
    done = dict(status)["조치 완료"]
    dist = lambda rows: [{"name": n, "reports": q(r, "건"), "qty": q(c, "개")} for n, r, c in rows]
    return {
        "id": "D", "key": "ops-quality", "name": "품질 · IT 운영", "task": "불량 보고 주간 요약",
        "question": "어떤 보고부터 확인해야 하고, 조치는 얼마나 진행됐는가",
        "flow": {
            "input": [q(reports, "건", "불량 보고"), q(qty, "개", "불량 수량")],
            "output": [q(3, "건", "조치 요청 메시지 (라인별)")],
            "review": [q(reports - done, "건", "미완료 조치"), q(2, "건", "원인 미기재")],
        },
        "view": "quality",
        "detail": {
            "order_basis": ["기록 누락", "반복 원인", "반복 유형", "불량 수량"],
            "order_groups": dist(groups),
            "status": [{"name": s, "reports": q(c, "건")} for s, c in status],
            "done": q(done, "건"), "reports": q(reports, "건"), "qty": q(qty, "개"),
            "types": dist(types),
            "lines": dist(lines),
            "daily": [{"date": d, "reports": q(r, "건"), "qty": q(c, "개")} for d, r, c in daily],
            "matrix": [{"line": l, "type": t, "reports": q(r, "건"), "qty": q(c, "개")} for l, t, r, c in sorted(cells)],
        },
    }


def build():
    tracks = []
    components = collect_components(REPO)
    for fn in (track_a, track_b, track_c, track_d):
        t = fn()
        t["verify"] = {"final": "DEMO"}
        t["sources"] = []
        t["components"] = components[t["key"]]
        tracks.append(t)
    return {
        "schema": 2,
        "title": "실습 결과 대시보드",
        "mode": "demo",
        "notice": "공개 데모입니다. 수치와 거래처 · 부서 · 과정 · 유형 명칭은 화면 구성을 보여주기 위한 가상의 예시이며, 검증 결과도 예시로만 표시합니다.",
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
