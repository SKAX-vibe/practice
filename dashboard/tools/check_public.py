"""공개 대상 파일 노출 점검.

공개 파일(index.html, styles.css, app.js, data/dashboard.json)에
개인정보 · 사번 · 품목별 단가 · 실습 정답 세부 내용이 없는지 검사한다.
금지어 일부는 원본 자료(직원명단 · 수료기록 · 단가표 · 정답 파일)에서 직접 뽑는다.

사용법 (저장소 최상위 폴더에서):
    python dashboard/tools/check_public.py dashboard          # 개발 폴더의 공개 파일 점검
    python dashboard/tools/check_public.py _site --strict     # 배포 폴더: 허용 목록 외 파일이 있으면 실패
"""

import argparse
import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

PUBLIC_FILES = ["index.html", "styles.css", "app.js", "data/dashboard.json"]
SITE_EXTRA = {".nojekyll"}

# 정답 파일의 '…' 표기 중, 대시보드가 집계 라벨로 쓰는 판정 · 분류명만 허용한다.
ALLOWED_LABELS = {"일치", "금액 차이", "계산서 없음", "지연", "확인 필요", "스크래치", "원인 미기재"}

PATTERNS = [
    ("사번", r"(?<![A-Za-z0-9])E\d{3}(?!\d)"),
    ("직원 가명", r"직원\d{2,}"),
    ("마스킹된 담당자명", r"[가-힣]OO"),
    ("이메일", r"[\w.+-]+@[\w-]+\.[\w.]+"),
    ("전화번호", r"(?<!\d)0\d{1,2}-\d{3,4}-\d{4}(?!\d)"),
    ("주민등록번호", r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)"),
    ("발주번호", r"PO-\d{4}-\d{3}"),
    ("계산서번호", r"TX-\d{3}"),
    ("개인정보 항목명", r"사번|이름|입사일|연락처"),
    ("단가 항목명", r"단가"),
    ("정답 언급", r"함정|정답"),
    ("원문 경로 참조", r"\.\./|outbox|drafts|inbox|answers|new-data|[\w-]+/data/\S*\.(?:csv|md)"),
]


def read_csv(rel):
    path = REPO / rel
    if not path.exists():
        sys.exit(f"[중단] 점검 기준 자료가 없습니다: {rel}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def dynamic_terms():
    """원본 자료에서 공개되면 안 되는 값을 모은다. (값, 사유) 목록."""
    terms = []
    for rel in ("hr-training/data/직원명단.csv", "new-data/L11/hr-training/data/직원명단_신규.csv"):
        for r in read_csv(rel):
            terms += [(r["사번"], "직원명단 사번"), (r["이름"], "직원명단 이름"), (r["입사일"], "직원명단 입사일")]
    for r in read_csv("hr-training/data/수료기록.csv"):
        terms.append((r["사번"], "수료기록 사번"))
    for r in read_csv("sales-quote/data/단가표.csv"):
        terms.append((r["품목"], "단가표 품목"))
        terms.append((f"{int(r['단가']):,}원", "단가표 단가"))

    answers = REPO / "answers" / "함정_정답.md"
    if not answers.exists():
        sys.exit("[중단] 점검 기준 자료가 없습니다: answers/함정_정답.md")
    for phrase in re.findall(r"'([^']+)'", answers.read_text(encoding="utf-8-sig")):
        if phrase not in ALLOWED_LABELS:
            terms.append((phrase, "정답 세부 항목"))
    return sorted(set(terms))


def term_regex(term):
    # 숫자로 시작하는 값(단가 · 날짜)은 더 긴 숫자의 일부로 잡히지 않게 경계를 둔다.
    pre = r"(?<![\d,])" if term[:1].isdigit() else ""
    return re.compile(pre + re.escape(term))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site", help="점검할 폴더 (dashboard 또는 배포용 _site)")
    ap.add_argument("--strict", action="store_true", help="허용 목록 외 파일이 있으면 실패")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    site = Path(args.site).resolve()
    problems = []

    present = {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()}
    for f in PUBLIC_FILES:
        if f not in present:
            problems.append(f"[누락] 공개 파일이 없습니다: {f}")
    if args.strict:
        for f in sorted(present - set(PUBLIC_FILES) - SITE_EXTRA):
            problems.append(f"[허용 외 파일] {f}")

    rules = [(name, re.compile(rx)) for name, rx in PATTERNS]
    rules += [(f"{why}: {term}", term_regex(term)) for term, why in dynamic_terms()]

    for f in PUBLIC_FILES:
        path = site / f
        if not path.exists():
            continue
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for name, rx in rules:
                m = rx.search(line)
                if m:
                    problems.append(f"[노출] {f}:{no} {name} → {m.group(0)!r}")

    print(f"점검 폴더: {site}")
    print(f"공개 파일 {len(PUBLIC_FILES)}개 · 규칙 {len(rules)}개 (고정 패턴 {len(PATTERNS)} + 원본 자료 금지어 {len(rules) - len(PATTERNS)})")
    print(f"허용한 집계 라벨: {', '.join(sorted(ALLOWED_LABELS))}")
    if problems:
        print(f"\nFAIL ({len(problems)}건)")
        print("\n".join(problems))
        sys.exit(1)
    print("\nPASS: 개인정보 · 사번 · 단가 · 정답 세부 내용 · 원문 경로 없음")


if __name__ == "__main__":
    main()
