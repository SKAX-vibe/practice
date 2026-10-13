"""report/교육이수.md 와 outbox/drafts/ 독려 초안을 data/ 원본과 대조해 PASS/FAIL 을 출력한다.

사용법: python scripts/verify.py
원본, 보고서, 초안은 읽기만 한다. 모두 일치하면 종료 코드 0, 불일치가 있으면 1.
- 명단은 data/직원명단*.csv 를 모두 읽어 사번 기준으로 합친다(L11 직원명단_신규.csv 대응).
- 개인 기한 = max(과정 기한, 입사일 + 신규 입사자 기한 일수).
- 수료 기록이 있으면 이수. 수료일이 개인 기한보다 늦으면 '기한 후 수료'로 따로 센다.
- 수료 기록이 없으면 미이수. 개인 기한이 기준일 전이면 '지연', 아니면 '기한 전'.
- 명단에 없는 사번의 수료 기록은 집계에서 빼고 '확인 필요'로 둔다.
- 독려 초안은 지연 인원에게만 쓴다(사번마다 outbox/drafts/독려_<사번>.md).
"""
import csv
import glob
import os
import re
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
REPORT = os.path.join(ROOT, "report", "교육이수.md")
DRAFT_DIR = os.path.join(ROOT, "outbox", "drafts")

LATE = "지연"
NOT_YET = "기한 전"


def read_csv(pattern):
    rows = []
    for path in sorted(glob.glob(os.path.join(DATA, pattern))):
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows.extend({k.strip(): v.strip() for k, v in r.items()} for r in csv.DictReader(f))
    return rows


def base_date():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        return date.fromisoformat(re.search(r"기준일은 (\d{4}-\d{2}-\d{2})", f.read()).group(1))


def load():
    roster = {r["사번"]: r for r in read_csv("직원명단*.csv")}
    courses = []
    for r in read_csv("교육과정.csv"):
        days = re.search(r"(\d+)일", r.get("신규 입사자 기한", ""))
        courses.append({"과정": r["과정"], "기한": date.fromisoformat(r["기한"]),
                        "신규일수": int(days.group(1)) if days else 0})
    done = {}
    unknown = []
    for r in read_csv("수료기록*.csv"):
        if r["사번"] not in roster:
            unknown.append((r["사번"], r["과정"]))
        else:
            done[(r["사번"], r["과정"])] = date.fromisoformat(r["수료일"])
    return roster, courses, done, sorted(unknown)


def analyze(roster, courses, done, today):
    stats, missing, late_done = [], [], []
    for c in courses:
        s = {"과정": c["과정"], "대상": len(roster), "이수": 0, "미이수": 0, LATE: 0, "기한 후": 0}
        for emp_id, emp in sorted(roster.items()):
            due = max(c["기한"], date.fromisoformat(emp["입사일"]) + timedelta(days=c["신규일수"]))
            finished = done.get((emp_id, c["과정"]))
            if finished:
                s["이수"] += 1
                if finished > due:
                    s["기한 후"] += 1
                    late_done.append((c["과정"], emp_id, finished.strftime("%m-%d")))
            else:
                s["미이수"] += 1
                status = LATE if due < today else NOT_YET
                if status == LATE:
                    s[LATE] += 1
                missing.append((c["과정"], emp_id, due.strftime("%m-%d"), status))
        stats.append(s)
    return stats, missing, late_done


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


def rate(done_count, total):
    return f"{done_count / total * 100:.1f}%" if total else "-"


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


def check_report(ck, stats, missing, late_done, unknown):
    if not ck.check("보고서 존재", os.path.exists(REPORT), True):
        return
    with open(REPORT, encoding="utf-8") as f:
        text = f.read()
    tables = read_tables(text)

    rows = {r[0]: r for r in tables.get("2", []) if len(r) >= 8}
    ck.check("2장 과정 목록", sorted(k for k in rows if k != "합계"), sorted(s["과정"] for s in stats))
    total = {"대상": 0, "이수": 0, "미이수": 0, LATE: 0, "기한 후": 0}
    for s in stats + [None]:
        if s is None:
            s = dict(total, 과정="합계")
        else:
            for k in total:
                total[k] += s[k]
        row = rows.get(s["과정"])
        actual = (tuple(to_int(c) for c in (row[2], row[3], row[4])) + (row[5],)
                  + tuple(to_int(c) for c in (row[6], row[7]))) if row else None
        ck.check(f"2장 {s['과정']} 대상/이수/미이수/이수율/지연/기한 후 수료", actual,
                 (s["대상"], s["이수"], s["미이수"], rate(s["이수"], s["대상"]), s[LATE], s["기한 후"]))
        if row and s["과정"] != "합계":
            ck.check(f"2장 {s['과정']} 이수 + 미이수 = 명단 인원",
                     (to_int(row[3]) or 0) + (to_int(row[4]) or 0), s["대상"])

    actual = sorted((r[0], r[1], r[4], r[5]) for r in tables.get("3", []) if len(r) >= 6)
    ck.check("3장 미이수자(과정, 사번, 개인 기한, 상태)", actual, sorted(missing))
    actual = sorted((r[0], r[1], r[4]) for r in tables.get("4", []) if len(r) >= 5)
    ck.check("4장 기한 후 수료(과정, 사번, 수료일)", actual, sorted(late_done))
    actual = sorted((r[0], r[1]) for r in tables.get("5", []) if len(r) >= 4)
    ck.check("5장 명단에 없는 사번(사번, 과정)", actual, unknown)

    late = [m for m in missing if m[3] == LATE]
    ck.check("요약 미이수 연인원/실인원",
             bool(re.search(rf"미이수 연인원 \*\*{len(missing)}명\*\*\(실인원 {len({m[1] for m in missing})}명\)", text)),
             True)
    ck.check("요약 지연 연인원/실인원",
             bool(re.search(rf"지연 \*\*{len(late)}명\*\*\(실인원 {len({m[1] for m in late})}명\)", text)), True)


def check_drafts(ck, missing, roster):
    late = {}
    for course, emp_id, due, status in missing:
        if status == LATE:
            late.setdefault(emp_id, []).append(course)
    files = sorted(re.match(r"독려_(.+)\.md$", os.path.basename(p)).group(1)
                   for p in glob.glob(os.path.join(DRAFT_DIR, "독려_*.md")))
    ck.check("독려 초안 대상 = 지연 인원(기한 전·명단 외 제외)", files, sorted(late))
    for emp_id in sorted(late):
        path = os.path.join(DRAFT_DIR, f"독려_{emp_id}.md")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        rows = read_tables(text).get("2", [])
        ck.check(f"독려_{emp_id} 이름", roster[emp_id]["이름"] in text, True)
        ck.check(f"독려_{emp_id} 미이수 과정/상태",
                 sorted((r[0], r[3]) for r in rows if len(r) >= 4), sorted((c, LATE) for c in late[emp_id]))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    today = base_date()
    roster, courses, done, unknown = load()
    stats, missing, late_done = analyze(roster, courses, done, today)

    print(f"기준일 {today} / 명단 {len(roster)}명 / 과정 {len(courses)}개")
    for s in stats:
        print(f"  {s['과정']}: 이수 {s['이수']} · 미이수 {s['미이수']} (지연 {s[LATE]}) · 기한 후 수료 {s['기한 후']}")
    print(f"  명단에 없는 사번: {unknown or '없음'}")
    print()

    ck = Checker()
    check_report(ck, stats, missing, late_done, unknown)
    check_drafts(ck, missing, roster)

    print()
    if ck.failures:
        print(f"결과: FAIL ({ck.failures}개 항목 불일치)")
        return 1
    print("결과: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
