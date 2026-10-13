"""공개용 데모 데이터 생성.

GitHub Pages에는 실제 실습 결과 대신 이 데모 데이터를 올린다.
아래 값은 화면 구성을 보여주기 위한 가상의 예시이며 저장소의 업무 파일을 읽지 않는다.
거래처 · 부서 · 과정 · 유형 명칭도 실제 자료와 겹치지 않는 예시 명칭만 쓴다.
구조는 build_data.py 가 만드는 data/dashboard.json 과 같다.

사용법 (저장소 최상위 폴더에서):
    python dashboard/tools/build_demo.py            # dashboard/data/demo.json 생성
    python dashboard/tools/build_demo.py --out X    # 다른 경로에 생성 (최신 여부 비교용)
"""

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "dashboard" / "data" / "demo.json"

DEMO = "예시"


def won(n):
    return f"{n:,}원"


def signed_won(n):
    return ("+" if n > 0 else "−" if n < 0 else "") + f"{abs(n):,}원"


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


def demo_verify():
    return {"final": "DEMO", "run_date": DEMO, "base_date": DEMO, "checks": [
        {"method": "자동 검증 스크립트 (예시)", "result": "DEMO"},
        {"method": "사실성 검토 (예시)", "result": "DEMO"},
    ]}


# ---------- 트랙별 예시 값 ----------

def track_a():
    quotes = [("샘플거래처 가", 4, 152000), ("샘플거래처 나", 3, 98500), ("샘플거래처 다", 2, 64000), ("샘플거래처 라", 2, 41500)]
    items = sum(q[1] for q in quotes)
    amount = sum(q[2] for q in quotes)
    return {
        "id": "A", "key": "sales-quote", "name": "영업", "desc": "견적 문의 회신",
        "kpis": [
            {"label": "견적 문의", "value": f"{len(quotes)}건", "sub": f"품목 {items}개"},
            {"label": "회신 초안", "value": f"{len(quotes)}건", "tone": "good"},
            {"label": "견적 금액 합계", "value": won(amount), "sub": "부가세 별도"},
            {"label": "확인 필요 품목", "value": "3개", "tone": "warn"},
        ],
        "charts": [{"type": "bar", "title": "거래처별 견적 금액",
                    "items": [{"label": n, "value": a, "display": won(a)} for n, _, a in quotes]}],
        "tables": [{
            "title": "거래처별 견적 집계",
            "headers": ["거래처", "품목 수", "견적 금액"],
            "align": ["left", "right", "right"],
            "rows": [[n, f"{i}개", won(a)] for n, i, a in quotes],
            "total": ["합계", f"{items}개", won(amount)],
        }],
    }


def track_b():
    courses = ["필수교육 A", "필수교육 B"]
    # 부서별 (대상, 과정별 이수)
    depts = [("부서 1", 9, (8, 7)), ("부서 2", 7, (6, 6)), ("부서 3", 8, (7, 5)), ("부서 4", 7, (5, 4))]
    total = sum(d[1] for d in depts)
    done = [sum(d[2][i] for d in depts) for i in range(len(courses))]
    late = [total - d for d in done]
    rows, total_rows = [], []
    for i, c in enumerate(courses):
        for name, size, comp in depts:
            rows.append([c, name, f"{size}명", f"{comp[i]}명", f"{size - comp[i]}명", f"{pct(comp[i], size):.1f}%", f"{size - comp[i]}명"])
        total_rows.append(len(rows))
        rows.append([c, "전체", f"{total}명", f"{done[i]}명", f"{late[i]}명", f"{pct(done[i], total):.1f}%", f"{late[i]}명"])
    return {
        "id": "B", "key": "hr-training", "name": "인사", "desc": "교육 이수 · 독려",
        "kpis": [
            *({"label": f"{c} 이수율", "value": f"{pct(done[i], total):.1f}%", "sub": f"이수 {done[i]}명 / 대상 {total}명"}
              for i, c in enumerate(courses)),
            {"label": "지연 (연인원)", "value": f"{sum(late)}명", "sub": "실인원 11명 · 독려 초안 11건", "tone": "warn"},
            {"label": "확인 필요 항목", "value": "3건", "sub": "담당자 판단 필요", "tone": "warn"},
        ],
        "charts": [{
            "type": "grouped", "title": "부서별 이수율", "series": courses, "max": 100,
            "ticks": ["0%", "25%", "50%", "75%", "100%"],
            "groups": [{"label": name, "values": [
                {"series": c, "value": pct(comp[i], size), "display": f"{pct(comp[i], size):.1f}%",
                 "tip": f"이수 {comp[i]}명 / 대상 {size}명"} for i, c in enumerate(courses)]}
                for name, size, comp in depts],
        }],
        "tables": [{
            "title": "과정 · 부서별 이수 현황",
            "headers": ["과정", "부서", "대상", "이수", "미이수", "이수율", "지연"],
            "align": ["left", "left", "right", "right", "right", "right", "right"],
            "rows": rows, "total_rows": total_rows,
        }],
    }


def track_c():
    # 판정별 (건수, 공급가액, 계산서 금액)
    stat = {"일치": (8, 9600000, 9600000), "금액 차이": (3, 3200000, 3080000), "계산서 없음": (1, 700000, 0)}
    diff = {s: (v[2] - v[1] if s != "계산서 없음" else 0) for s, v in stat.items()}
    count = sum(v[0] for v in stat.values())
    supply = sum(v[1] for v in stat.values())
    invoice = sum(v[2] for v in stat.values())
    diff_total = sum(diff.values())
    return {
        "id": "C", "key": "fin-invoice", "name": "재무 · 구매", "desc": "발주 · 세금계산서 대조",
        "kpis": [
            {"label": "발주", "value": f"{count}건", "sub": f"계산서 대응 {count - stat['계산서 없음'][0]}건"},
            {"label": "일치", "value": f"{stat['일치'][0]}건", "tone": "good"},
            {"label": "불일치", "value": f"{stat['금액 차이'][0] + stat['계산서 없음'][0]}건", "sub": "확인 요청 초안 4건", "tone": "warn"},
            {"label": "차액 합계", "value": signed_won(diff_total), "sub": "계산서 − 공급가액"},
        ],
        "charts": [{"type": "status", "title": "판정 구성", "items": [{"name": s, "count": v[0]} for s, v in stat.items()]}],
        "tables": [{
            "title": "판정별 집계",
            "headers": ["판정", "건수", "공급가액", "계산서 금액", "차액"],
            "align": ["left", "right", "right", "right", "right"],
            "status_col": 0,
            "rows": [[s, f"{v[0]}건", won(v[1]), won(v[2]), signed_won(diff[s])] for s, v in stat.items()],
            "total": ["합계", f"{count}건", won(supply), won(invoice), signed_won(diff_total)],
        }],
    }


def track_d():
    types = [("이물 혼입", 4, 21), ("치수 불량", 2, 17), ("도장 불량", 2, 14)]
    lines = [("가", 3, 20), ("나", 3, 18), ("다", 2, 14)]
    status = [("조치 중", 4), ("조치 미기재", 1), ("조치 완료", 3)]
    reports = sum(t[1] for t in types)
    qty = sum(t[2] for t in types)
    assert reports == sum(l[1] for l in lines) == sum(s[1] for s in status) and qty == sum(l[2] for l in lines)
    done = dict(status)["조치 완료"]
    bar = lambda label, n, q: {"label": label, "value": q, "display": f"{q}개", "tip": f"{n}건 · {q}개"}
    return {
        "id": "D", "key": "ops-quality", "name": "품질 · IT 운영", "desc": "불량 보고 주간 요약",
        "kpis": [
            {"label": "불량 보고", "value": f"{reports}건"},
            {"label": "불량 수량", "value": f"{qty}개"},
            {"label": "미완료 조치", "value": f"{reports - done}건", "sub": f"조치 완료 {done}건", "tone": "warn"},
            {"label": "원인 미기재", "value": "2건", "tone": "warn"},
        ],
        "charts": [
            {"type": "bar", "title": "유형별 불량 수량", "items": [bar(*t) for t in types]},
            {"type": "bar", "title": "라인별 불량 수량", "items": [bar(f"{n}라인", c, q) for n, c, q in lines]},
        ],
        "tables": [{
            "title": "조치 상태별 집계",
            "headers": ["조치 상태", "보고 건수"],
            "align": ["left", "right"],
            "rows": [[s, f"{c}건"] for s, c in status],
            "total": ["합계", f"{reports}건"],
        }],
    }


def build():
    tracks = []
    for fn in (track_a, track_b, track_c, track_d):
        t = fn()
        t["verify"] = demo_verify()
        t["sources"] = []
        tracks.append(t)
    return {
        "title": "실습 결과 대시보드",
        "mode": "demo",
        "notice": "이 화면의 수치 · 거래처 · 부서 · 과정 · 유형 명칭은 대시보드 구성을 보여주기 위한 가상의 예시입니다. 실제 실습 결과나 검증 결과가 아닙니다.",
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
