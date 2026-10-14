# 실습 결과 대시보드

A·B·C·D 트랙 결과물의 집계와 검증 결과를 한 화면에서 보는 정적 페이지이다.
HTML · CSS · JavaScript만 사용하며, DB · 백엔드가 없다.

## 화면 구성

| 화면 | 주소 | 핵심 질문 | 중심 요소 |
|---|---|---|---|
| 개요 | `#overview` | 자동화가 무엇을 처리했고, 사람이 무엇을 판단해야 하나 | 트랙별 입력 → 자동 산출 → 사람 확인 → 검증 |
| A 영업 | `#A` | 바로 보낼 회신과 확인할 항목은 | 문의별 처리 목록 |
| B 인사 | `#B` | 이수 정도와 지연자 독려 준비 여부 | 과정별 이수율 · 부서 × 과정 행렬 · 지연 → 독려 연결 |
| C 재무 · 구매 | `#C` | 자동 대조 결과와 어긋난 곳 | 판정 구성 · 판정별 금액 · 불일치 → 확인 요청 연결 |
| D 품질 · IT | `#D` | 어떤 보고부터 확인하고 조치는 얼마나 진행됐나 | 확인 순서(정렬 기준, 확정 판정 아님) · 조치 진행 · 불량 분포 |

개요 하단 "자동화 구성 요소"는 각 업무 폴더에 실제로 있는 도구 · Skill · 커맨드 · Memory 목록이다(`tools/components.py`). 파일이 없으면 표시하지 않고, 목록에 없는 새 파일이 생기면 데이터 생성이 실패한다.

디자인 기준: `design/design.md` (레이아웃 · 타이포그래피 · 여백 · 정보 위계 참고, 브랜드 요소 미사용, 밝은 테마만).
데이터 구조는 `schema: 2`이며 모든 수치는 `{value, unit}`(건 · 명 · 개 · 원 · % · 항목 · 곳)로 단위를 함께 담는다.

## 데이터 두 종류

화면은 `data/dashboard.json` 한 파일만 읽는다. 어떤 데이터를 넣느냐에 따라 화면 상단에 종류가 표시된다.

| 파일 | 종류 | 용도 | 화면 표시 |
|---|---|---|---|
| `data/dashboard.json` | 내부 실습 결과 (`mode: internal`) | 로컬 확인용. 공개하지 않는다 | 상단 "내부 확인용" 표시 |
| `data/demo.json` | 가상 데모 데이터 (`mode: demo`) | GitHub Pages 공개용 | 상단 "DEMO · 예시 데이터" 표시, 개요 안내 한 줄, 검증 결과는 수치 없이 "예시" |

- 내부 데이터는 `tools/build_data.py`가 각 트랙 `report/`에서 집계만 뽑아 만든다. 사번 · 이름 · 입사일, 품목명 · 단가, 발주 · 계산서 번호, 확인 필요 항목 내용, 원문은 넣지 않는다. 대상 3명 미만 부서는 '기타 N개 부서'로 합산한다.
- 데모 데이터는 `tools/build_demo.py`에 적은 가상의 예시 값이다. 업무 파일을 읽지 않으며 거래처 · 부서 · 과정 · 유형 이름도 예시 이름만 쓴다.

## 구성

| 경로 | 공개 | 역할 |
|---|---|---|
| `index.html`, `styles.css`, `app.js` | O | 화면 |
| `data/demo.json` | O (사이트에는 `data/dashboard.json` 이름으로 올라감) | 공개용 데모 데이터 |
| `data/dashboard.json` | X | 내부 실습 결과 집계 |
| `tools/build_data.py`, `tools/build_demo.py`, `tools/components.py` | X | 데이터 생성 · 구성 요소 목록 |
| `tools/check_public.py` | X | 공개 파일 노출 점검 |

배포 워크플로: `.github/workflows/pages.yml`

## 데이터 갱신 · 점검

저장소 최상위 폴더에서 실행한다.

```
python dashboard/tools/build_data.py          # 내부 집계 갱신
python dashboard/tools/build_demo.py          # 데모 데이터 갱신
python dashboard/tools/check_public.py dashboard
```

공개 사이트와 같은 구성으로 점검하려면 공개 파일 4개를 `_site/`에 모은 뒤(`demo.json` → `_site/data/dashboard.json`) 다음을 실행한다.

```
python dashboard/tools/check_public.py _site --strict --demo
```

- 고정 패턴: 사번 · 직원 가명 · 담당자명 · 연락처 · 주민번호 · 발주 · 계산서 번호 · `단가` 같은 항목명 · 원문 경로
- 원본 자료 금지어: 직원명단 · 수료기록의 사번 · 이름 · 입사일, 단가표의 품목 · 단가, 정답 파일의 세부 항목
- `--strict`: 공개 파일 4개 외 파일이 있으면 실패
- `--demo`: 공개 데이터가 `mode: demo`인지, 실제 집계 값(숫자 10 이상이 들어간 값) · 실제 거래처명이 섞이지 않았는지 확인

## 로컬에서 보기

```
cd dashboard
python -m http.server 8000
```

`http://localhost:8000/` 을 연다 (내부 실습 결과 표시). 트랙은 `#A` ~ `#D` 주소로 바로 열 수 있다. 서버는 그 터미널에서 Ctrl+C로 끈다.

## GitHub Pages 배포

`.github/workflows/pages.yml`은 수동 실행만 허용한다.

1. GitHub 저장소 Settings → Pages → Build and deployment → Source: **GitHub Actions**
2. Actions 탭 → "Deploy dashboard to GitHub Pages" → **Run workflow**
3. 배포 주소: `https://<owner>.github.io/<repo>/`

워크플로 순서: `demo.json`이 `build_demo.py` 결과와 같은지 확인 → 공개 파일 3개 + 데모 데이터만 `_site/`에 복사 → `check_public.py _site --strict --demo` → 배포. 점검에서 하나라도 걸리면 배포하지 않는다.
