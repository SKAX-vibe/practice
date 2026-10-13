"""report/교육이수.md 와 outbox/drafts/ 독려 초안을 data/ 원본과 대조해 PASS/FAIL 을 출력한다.

사용법: python scripts/verify.py
원본, 보고서, 초안은 읽기만 한다. 모두 일치하면 종료 코드 0, 불일치가 있으면 1.

공식 형식(교육자료 L03 · 부록 B 트랙 B): 부서별 이수율 표 → 미이수자 목록 순서.
- 명단은 data/직원명단*.csv 를 모두 읽어 사번 기준으로 합친다(L11 직원명단_신규.csv 대응).
  같은 사번의 내용이 파일마다 다르면 '명단 중복 불일치'로 확인 필요.
- 기한: 신규 입사자 판별에 일반화 규칙을 쓰지 않는다. 원본·정답에 명시된 사번만 판별한다.
  - 기존 직원 = 원본 명단(data/직원명단.csv)의 사번: 과정 기한 (answers/함정_정답.md "명단 12명 ... 기한 2026-06-10")
  - 신규 입사자 예외 = data/신규입사자예외.csv 의 사번(근거가 적힌 행만): 입사일 + N일,
    N은 교육과정.csv 의 '신규 입사자 기한'. 근거가 빈 행은 예외로 인정하지 않고 '확인 필요'(예외 근거 누락).
    예외 사번 추가는 담당자가 이 파일에 한다. 스크립트는 수정하지 않는다.
  - 그 외 사번, 또는 예외 사번의 입사일·N을 읽을 수 없으면 신규 입사자 여부 확인 불가 → '확인 필요'
- 수료 기록이 있으면 이수. 수료일이 기한보다 늦으면 이수로 세고 '기한 후 수료'로 확인 필요.
- 수료 기록이 없으면 미이수. 기한이 기준일 전이면 '지연', 아니면 '기한 전', 기한 판별 불가면 '확인 필요'.
- 명단에 없는 사번, 교육과정.csv 에 없는 과정명의 수료 기록은 집계에서 빼고 '확인 필요'.
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

LATE, NOT_YET, UNSURE = "지연", "기한 전", "확인 필요"
BASIS_COURSE, BASIS_NEW = "과정 기한", "신규 입사자 예외"
BASE_ROSTER = "직원명단.csv"  # 기존 직원 명단(원본 12명)
NEW_HIRE_FILE = "신규입사자예외.csv"  # 사번,근거. Skill 과 같은 파일을 참조한다.
ALL_DEPTS = "전체"
NOTE_UNKNOWN_ID = "명단에 없는 사번"
NOTE_LATE_DONE = "기한 후 수료"
NOTE_NEW_HIRE = "신규 입사자 여부 확인 불가"
NOTE_COURSE = "과정명 불일치"
NOTE_DUP = "명단 중복 불일치"
NOTE_NO_BASIS = "예외 근거 누락"
SECTIONS = [("1", "부서별 이수율"), ("2", "미이수자 목록"), ("3", "확인 필요 항목")]


def read_csv(pattern):
    rows = []
    for path in sorted(glob.glob(os.path.join(DATA, pattern))):
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows.extend({k.strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f))
    return rows


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def base_date():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        return date.fromisoformat(re.search(r"기준일은 (\d{4}-\d{2}-\d{2})", f.read()).group(1))


def load():
    notes = set()
    base_ids = {r["사번"] for r in read_csv(BASE_ROSTER)}
    new_hire_ids = set()
    for r in read_csv(NEW_HIRE_FILE):
        if r.get("근거"):
            new_hire_ids.add(r["사번"])
        else:
            notes.add((NOTE_NO_BASIS, r["사번"], "-"))
    roster = {}
    for r in read_csv("직원명단*.csv"):
        if r["사번"] in roster and roster[r["사번"]] != r:
            notes.add((NOTE_DUP, r["사번"], "-"))
        roster.setdefault(r["사번"], r)
    courses = []
    for r in read_csv("교육과정.csv"):
        days = re.search(r"(\d+)일", r.get("신규 입사자 기한", ""))
        courses.append({"과정": r["과정"], "기한": date.fromisoformat(r["기한"]),
                        "신규일수": int(days.group(1)) if days else None})
    names = {c["과정"] for c in courses}
    done = {}
    for r in read_csv("수료기록*.csv"):
        if r["사번"] not in roster:
            notes.add((NOTE_UNKNOWN_ID, r["사번"], r["과정"]))
        elif r["과정"] not in names:
            notes.add((NOTE_COURSE, r["사번"], r["과정"]))
        else:
            done[(r["사번"], r["과정"])] = date.fromisoformat(r["수료일"])
    return roster, courses, done, notes, base_ids, new_hire_ids


def deadline(emp_id, emp, course, base_ids, new_hire_ids):
    """(기한 또는 None, 기한 기준). None 이면 신규 입사자 여부를 확인할 수 없다."""
    if emp_id in new_hire_ids:
        hired = parse_date(emp.get("입사일", ""))
        if hired is None or course["신규일수"] is None:
            return None, UNSURE
        return hired + timedelta(days=course["신규일수"]), BASIS_NEW
    if emp_id in base_ids:
        return course["기한"], BASIS_COURSE
    return None, UNSURE


def analyze(roster, courses, done, notes, base_ids, new_hire_ids, today):
    depts = list(dict.fromkeys(e["부서"] for e in roster.values()))
    stats = {}
    missing = []
    for c in courses:
        for dept in depts + [ALL_DEPTS]:
            stats[(c["과정"], dept)] = {"대상": 0, "이수": 0, "미이수": 0, LATE: 0, NOT_YET: 0, UNSURE: 0, "기한 후": 0}
        for emp_id, emp in sorted(roster.items()):
            due, basis = deadline(emp_id, emp, c, base_ids, new_hire_ids)
            if due is None:
                notes.add((NOTE_NEW_HIRE, emp_id, c["과정"]))
            buckets = [stats[(c["과정"], emp["부서"])], stats[(c["과정"], ALL_DEPTS)]]
            finished = done.get((emp_id, c["과정"]))
            if finished:
                key = "이수"
                if due and finished > due:
                    notes.add((NOTE_LATE_DONE, emp_id, c["과정"]))
                    for s in buckets:
                        s["기한 후"] += 1
            else:
                status = UNSURE if due is None else (LATE if due < today else NOT_YET)
                key = "미이수"
                for s in buckets:
                    s[status] += 1
                missing.append((c["과정"], emp_id, due.strftime("%m-%d") if due else UNSURE, status))
            for s in buckets:
                s["대상"] += 1
                s[key] += 1
    return depts, stats, missing


def read_sections(text):
    """'## N. 제목' 섹션 번호 -> (제목, 표 본문 행 목록)."""
    sections = {}
    for section in re.split(r"^## ", text, flags=re.M)[1:]:
        head = section.splitlines()[0]
        number, _, title = head.partition(".")
        rows = [
            [c.strip().strip("*").strip() for c in line.strip().strip("|").split("|")]
            for line in section.splitlines()
            if line.startswith("|")
        ]
        sections[number.strip()] = (title.strip(), rows[2:])  # 머리글과 구분선 제외
    return sections


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


def check_report(ck, roster, courses, depts, stats, missing, notes):
    if not ck.check("보고서 존재", os.path.exists(REPORT), True):
        return
    with open(REPORT, encoding="utf-8") as f:
        text = f.read()
    sections = read_sections(text)

    ck.check("공식 형식 장 구성(부서별 이수율 → 미이수자 목록 → 확인 필요 항목)",
             [(n, sections.get(n, ("", []))[0]) for n, _ in SECTIONS], SECTIONS)

    rows = {(r[0], r[1]): r for r in sections.get("1", ("", []))[1] if len(r) >= 10}
    ck.check("1장 과정·부서 목록", sorted(rows), sorted(stats))
    for (course, dept), s in stats.items():
        row = rows.get((course, dept))
        actual = None
        if row:
            actual = tuple(to_int(c) for c in row[2:5]) + (row[5],) + tuple(to_int(c) for c in row[6:10])
        ck.check(f"1장 {course} {dept} 대상/이수/미이수/이수율/지연/기한 전/확인 필요/기한 후 수료", actual,
                 (s["대상"], s["이수"], s["미이수"], rate(s["이수"], s["대상"]),
                  s[LATE], s[NOT_YET], s[UNSURE], s["기한 후"]))
    for c in courses:
        row = rows.get((c["과정"], ALL_DEPTS))
        ck.check(f"1장 {c['과정']} 이수 + 미이수 = 명단 인원",
                 (to_int(row[3]) or 0) + (to_int(row[4]) or 0) if row else None, len(roster))

    actual = sorted((r[0], r[1], r[5], r[7]) for r in sections.get("2", ("", []))[1] if len(r) >= 8)
    ck.check("2장 미이수자(과정, 사번, 기한, 상태)", actual, sorted(missing))

    actual = sorted((r[0], r[1], r[2]) for r in sections.get("3", ("", []))[1] if len(r) >= 4)
    ck.check("3장 확인 필요(구분, 사번, 과정)", actual, sorted(notes))

    late = [m for m in missing if m[3] == LATE]
    ck.check("머리 미이수 연인원/실인원",
             bool(re.search(rf"미이수 연인원 \*\*{len(missing)}명\*\*\(실인원 {len({m[1] for m in missing})}명\)", text)),
             True)
    ck.check("머리 지연 연인원/실인원",
             bool(re.search(rf"지연 \*\*{len(late)}명\*\*\(실인원 {len({m[1] for m in late})}명\)", text)), True)


def check_drafts(ck, missing, roster):
    late = {}
    for course, emp_id, due, status in missing:
        if status == LATE:
            late.setdefault(emp_id, []).append(course)
    files = sorted(re.match(r"독려_(.+)\.md$", os.path.basename(p)).group(1)
                   for p in glob.glob(os.path.join(DRAFT_DIR, "독려_*.md")))
    ck.check("독려 초안 대상 = 지연 인원(기한 전·확인 필요·명단 외 제외)", files, sorted(late))
    for emp_id in sorted(late):
        path = os.path.join(DRAFT_DIR, f"독려_{emp_id}.md")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        rows = read_sections(text).get("2", ("", []))[1]
        ck.check(f"독려_{emp_id} 이름", roster[emp_id]["이름"] in text, True)
        ck.check(f"독려_{emp_id} 미이수 과정/상태",
                 sorted((r[0], r[3]) for r in rows if len(r) >= 4), sorted((c, LATE) for c in late[emp_id]))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    today = base_date()
    roster, courses, done, notes, base_ids, new_hire_ids = load()
    depts, stats, missing = analyze(roster, courses, done, notes, base_ids, new_hire_ids, today)

    print(f"기준일 {today} / 명단 {len(roster)}명 / 부서 {len(depts)}개 / 과정 {len(courses)}개")
    for c in courses:
        s = stats[(c["과정"], ALL_DEPTS)]
        print(f"  {c['과정']}: 이수 {s['이수']} · 미이수 {s['미이수']} "
              f"(지연 {s[LATE]}, 기한 전 {s[NOT_YET]}, 확인 필요 {s[UNSURE]}) · 기한 후 수료 {s['기한 후']}")
    new_hires = sorted({e for e, emp in roster.items() for c in courses if deadline(e, emp, c, base_ids, new_hire_ids)[1] == BASIS_NEW})
    print(f"  신규 입사자 예외 적용: {new_hires or '없음'}")
    print(f"  확인 필요: {sorted(notes) or '없음'}")
    print()

    ck = Checker()
    check_report(ck, roster, courses, depts, stats, missing, notes)
    check_drafts(ck, missing, roster)

    print()
    if ck.failures:
        print(f"결과: FAIL ({ck.failures}개 항목 불일치)")
        return 1
    print("결과: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
