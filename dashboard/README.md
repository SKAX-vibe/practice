# 실습 결과 대시보드

A·B·C·D 트랙 결과물의 집계와 검증 결과를 한 화면에서 보는 정적 페이지이다.
HTML · CSS · JavaScript만 사용하며, DB · 백엔드가 없다.

## 구성

| 경로 | 공개 | 역할 |
|---|---|---|
| `index.html`, `styles.css`, `app.js` | O | 화면 |
| `data/dashboard.json` | O | 공개용 집계 데이터. 화면은 이 파일만 읽는다 |
| `tools/build_data.py` | X | 각 트랙 `report/`에서 집계를 뽑아 `data/dashboard.json` 생성 |
| `tools/check_public.py` | X | 공개 파일 노출 점검 |
| `deploy/pages.yml` | X | Pages 배포 워크플로 템플릿 (비활성) |

## 공개 데이터 기준

`data/dashboard.json`에는 집계 수치와 검증 통과 여부만 넣는다.

- 넣는 것: 트랙별 건수 · 금액 합계 · 이수율 · 판정별 건수, 거래처별 견적 합계, 유형 · 라인별 불량 수량, 검증 결과(PASS/FAIL, 통과 항목 수)
- 빼는 것: 사번 · 이름 · 입사일, 품목명 · 단가, 발주 · 계산서 번호, 확인 필요 항목의 내용, 보고서 · 초안 원문
- 대상 3명 미만 부서는 '기타 N개 부서'로 합산한다 (`build_data.py`의 `MIN_GROUP`)

판정별 건수 같은 집계 수치는 실습 정답의 집계 수치와 같다. 어느 건이 어떤 판정인지 같은 세부 내용은 넣지 않는다.

## 데이터 갱신

보고서를 다시 만든 뒤 저장소 최상위 폴더에서 실행한다.

```
python dashboard/tools/build_data.py
python dashboard/tools/check_public.py dashboard
```

`check_public.py`는 고정 패턴(사번 · 발주번호 · 연락처 등)과 원본 자료에서 뽑은 금지어(직원명단 · 수료기록의 사번 · 이름 · 입사일, 단가표의 품목 · 단가, 정답 파일의 세부 항목)로 공개 파일을 검사한다. 하나라도 걸리면 FAIL로 끝난다.

## 로컬에서 보기

```
cd dashboard
python -m http.server 8000
```

`http://localhost:8000/` 을 연다 (배포 사이트와 같은 구조). 트랙은 `#A` ~ `#D` 주소로 바로 열 수 있다. 서버는 그 터미널에서 Ctrl+C로 끈다.

## GitHub Pages 배포 (현재 비활성)

`deploy/pages.yml`은 실행되지 않는 템플릿이다. 공개 승인 후 절차:

1. `dashboard/deploy/pages.yml` 을 `.github/workflows/pages.yml` 로 복사해 커밋 · push
2. GitHub 저장소 Settings → Pages → Build and deployment → Source: **GitHub Actions**
3. Actions 탭 → "Deploy dashboard to GitHub Pages" → **Run workflow** (수동 실행만 허용)
4. 배포 주소: `https://<owner>.github.io/<repo>/`

워크플로 순서: `data/dashboard.json`이 최신 결과물과 같은지 확인 → 공개 파일 4개만 `_site/`에 복사 → `check_public.py _site --strict` (허용 목록 외 파일 · 노출 항목이 있으면 중단) → 배포.
