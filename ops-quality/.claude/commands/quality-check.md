---
description: 보고서를 만들거나 고치지 않고, 기존 품질 보고서를 원본과 대조해 검증만 한다
argument-hint: "[all | weekly | draft]"
allowed-tools: Bash(python scripts/verify.py), Read, Grep, Glob
---

# 품질 보고서 검증 (읽기 전용)

검증 범위: `$ARGUMENTS`

이 커맨드는 검증만 한다. 보고서 생성, 문장 수정, `report/검증결과.md` 저장은 `quality-weekly` Skill이 맡는다.
업무 규칙(유형 정규화, 표기, 제약)은 `CLAUDE.md`를 따른다.

## 범위
| 인자 | 검증 대상 | 방법 |
|---|---|---|
| `weekly` | `report/품질주간.md` | 집계 검증 |
| `draft` | `report/조치요청초안.md` | 사실성 검토 |
| `all` 또는 빈 값 | 두 파일 모두 | 두 방법 모두 |

위 세 가지가 아닌 값이면 검증하지 말고 사용 가능한 값을 알려 준다.

## 절차
1. `CLAUDE.md`와 `data/불량보고/*.md`를 읽는다. 대상 파일이 없으면 해당 대상은 FAIL(파일 없음)로 처리한다.
2. **집계 검증** (`weekly`, `all`): `python scripts/verify.py`를 실행한다.
   - 마지막 줄의 `결과: PASS` 또는 `결과: FAIL`을 그대로 쓴다.
   - FAIL이면 `[FAIL]` 항목과 기대값을 옮긴다.
3. **사실성 검토** (`draft`, `all`): `.claude/skills/quality-weekly/SKILL.md`의 5-2 기준으로 초안을 원본과 대조한다.
   - 문장을 원본 사실 / AI 제안 / 근거 없는 추론으로 구분한다.
   - 근거 없는 추론이 하나라도 있으면 FAIL이다. 문장은 고치지 않고 위치와 이유만 보고한다.
   - 숫자는 원본 집계와 같은지 확인한다(유형은 `CLAUDE.md` 정규화 기준 적용).
4. 어떤 파일도 만들거나 수정하지 않는다. 원본 데이터, 보고서, 스크립트, 검증결과 모두 해당한다.

## 출력
```
검증 범위: <weekly | draft | all>
| 검증 대상 | 방법 | 결과 | 실패 사유 |
최종: PASS | FAIL
```
- 최종 결과는 검증한 대상이 모두 PASS일 때만 PASS다.
- 실패 사유는 항목, 위치(행 번호), 기대값 또는 원본 값을 한 줄씩 적는다.
- FAIL이면 마지막에 "수정과 결과 저장은 `/quality-weekly`로 진행"이라고 안내한다.
