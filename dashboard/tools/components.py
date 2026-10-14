"""업무(트랙)별 '자동화 구성 요소' 목록.

각 트랙 폴더의 커맨드 · Skill · 도구 · 기억 파일 중 **실제로 존재하는 것만** 그 트랙 페이지에 넣는다.
설명은 아래 CATALOG에 짧게 적는다(파일 내용 · 실행 명령은 넣지 않음).
여러 트랙에 같은 이름의 파일이 있으면(verify.py) 트랙별 실제 경로와 그 파일이 검증하는 대상을 따로 적는다.
트랙 폴더에 CATALOG에 없는 커맨드 · Skill · 도구 · 기억 파일이 새로 생기면 오류를 낸다(누락 방지).
"""

from pathlib import Path

TRACK_KEYS = ["sales-quote", "hr-training", "fin-invoice", "ops-quality"]

# 트랙별 verify.py 역할: 각 파일 docstring 첫 줄의 검증 대상을 옮긴 것
VERIFY_DESC = {
    "sales-quote": "회신 초안과 견적 처리 현황을 문의 원문 · 단가표와 대조해 PASS/FAIL로 검증",
    "hr-training": "교육 이수 현황과 독려 초안을 원본 자료와 대조해 PASS/FAIL로 검증",
    "fin-invoice": "대조표 · 대조 요약 · 확인 요청 초안을 원본 자료와 대조해 PASS/FAIL로 검증",
    "ops-quality": "주간 품질 보고서를 불량 보고 원본과 대조해 PASS/FAIL로 검증",
}

# (구분, 표시 이름, 트랙 폴더 기준 상대 경로, 설명 — 문자열 또는 트랙별 dict)
CATALOG = [
    ("도구", "price_lookup.py", "tools/price_lookup.py",
     "품목명과 단위를 기준으로 단가표를 조회하고 불일치 항목을 확인 필요로 분류"),
    ("도구", "verify.py", "scripts/verify.py", VERIFY_DESC),
    ("Skill", "quote-reply", ".claude/skills/quote-reply/SKILL.md",
     "회신 초안이 없는 견적 문의를 찾아 초안과 처리 현황을 작성하고 검증 결과를 남김"),
    ("Skill", "reply-rules", ".claude/skills/reply-rules/SKILL.md",
     "견적 회신 초안의 문구 규칙과 사용하지 않는 표현 관리"),
    ("Skill", "training-nudge", ".claude/skills/training-nudge/SKILL.md",
     "교육 이수 현황을 정리하고 기한이 지난 미이수자에게 보낼 독려 초안을 작성한 뒤 검증"),
    ("Skill", "invoice-check", ".claude/skills/invoice-check/SKILL.md",
     "발주와 세금계산서를 대조하고 불일치 거래처별 확인 요청 초안을 작성한 뒤 검증"),
    ("Skill", "quality-weekly", ".claude/skills/quality-weekly/SKILL.md",
     "주간 품질 보고서를 만들고 반복 · 미조치 분석과 조치 요청 초안까지 작성"),
    ("커맨드", "/quote", ".claude/commands/quote.md",
     "견적 문의를 단가표와 대조해 회신 초안을 작성하고 검증"),
    ("커맨드", "/training", ".claude/commands/training.md",
     "명단과 수료 기록을 대조해 부서별 이수율과 미이수자 목록을 작성하고 검증"),
    ("커맨드", "/match", ".claude/commands/match.md",
     "발주와 세금계산서를 대조해 대조표와 차이 목록을 작성하고 검증"),
    ("커맨드", "/weekly", ".claude/commands/weekly.md",
     "불량 보고를 유형별로 집계해 주간 품질 보고서를 작성하고 검증"),
    ("커맨드", "/quality-check", ".claude/commands/quality-check.md",
     "보고서를 고치지 않고 원본과 대조해 검증만 수행"),
    ("Memory", "견적업무기억.md", "memory/견적업무기억.md",
     "거래처 문의 이력과 업무상 확인 사항을 날짜 및 출처와 함께 기록"),
]

KIND_ORDER = ["도구", "Skill", "커맨드", "Memory"]


def _existing_files(track_dir):
    """트랙 폴더의 커맨드 · Skill · 도구 · 기억 파일(.gitkeep 등 제외)."""
    patterns = [".claude/commands/*.md", ".claude/skills/*/SKILL.md", "tools/*.py", "memory/*.md", "scripts/*.py"]
    return {p.relative_to(track_dir).as_posix() for pat in patterns for p in track_dir.glob(pat) if p.is_file()}


def collect(repo):
    """{트랙 키: [{kind, name, path, desc}, ...]} — 트랙 폴더에 실제로 있는 항목만."""
    repo = Path(repo)
    cataloged = {rel for _, _, rel, _ in CATALOG}
    unknown = []
    for key in TRACK_KEYS:
        unknown += [f"{key}/{rel}" for rel in sorted(_existing_files(repo / key) - cataloged)]
    if unknown:
        raise ValueError(f"구성 요소 목록(CATALOG)에 없는 파일이 있습니다: {unknown}")

    result = {}
    for key in TRACK_KEYS:
        items = []
        for kind, name, rel, desc in CATALOG:
            if not (repo / key / rel).is_file():
                continue
            text = desc[key] if isinstance(desc, dict) else desc
            items.append({"kind": kind, "name": name, "path": f"{key}/{rel}", "desc": text})
        items.sort(key=lambda x: KIND_ORDER.index(x["kind"]))
        result[key] = items
    return result
