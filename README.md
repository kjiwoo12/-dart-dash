# DART 재무분석기

DART(전자공시시스템) Open API를 이용해 회사명으로 검색한 3개 회사의 연결재무제표를 최근 3개년 기준으로 비교하고, 결과를 엑셀 파일로 저장하는 도구입니다. CLI(`main.py`)와 웹 UI(`api/index.py`, Vercel 배포용) 두 가지 방식으로 사용할 수 있으며 핵심 로직(`dart_lib/`)을 공유합니다.

## 설치

```
pip install -r requirements.txt
```

## API 키 설정

1. `.env.example` 파일을 `.env`로 복사합니다.
2. [OpenDART](https://opendart.fss.or.kr)에서 발급받은 인증키를 `.env`의 `DART_API_KEY` 값으로 입력합니다.

```
DART_API_KEY=발급받은_API_키
```

`.env` 파일은 `.gitignore`에 포함되어 있어 커밋되지 않습니다.

## 실행

```
python main.py
```

실행하면 비교할 회사 3곳의 이름을 순서대로 입력하라는 프롬프트가 나옵니다. 검색 결과가 여러 건이면 후보 목록에서 번호로 선택합니다.

비교 연도를 직접 지정하려면:

```
python main.py --years 2022,2023,2024
```

옵션을 생략하면 최근 확정된 3개 사업연도를 자동으로 사용합니다(12월 결산법인 기준, 4월 이후에는 전년도까지 확정된 것으로 간주).

## 출력물

`output/재무분석_YYYYMMDD_HHMMSS.xlsx` 형식으로 저장되며 다음 4개 시트로 구성됩니다.

- **비교요약**: 연도별로 3개 회사를 나란히 놓고 9개 재무항목 + ROE + 부채비율을 비교
- **회사명 시트 (3개)**: 각 회사의 연도별 상세 수치

조회 항목: 자산총계·부채총계·자본총계(재무상태표), 매출액·영업이익·당기순이익(손익계산서), 영업/투자/재무활동현금흐름(현금흐름표), ROE(%)·부채비율(%)(계산 지표).

## 웹 UI (로컬 실행 / Vercel 배포)

로컬에서 웹 UI를 실행하려면:

```
python api/index.py
```

브라우저에서 `http://127.0.0.1:5000` 접속 → 회사명 3곳 입력(자동완성 지원) → 비교 결과 표 확인 → "엑셀 다운로드" 버튼으로 파일 저장.

**Vercel 배포**
1. 이 저장소를 GitHub에 push
2. [Vercel 대시보드](https://vercel.com)에서 "Add New Project → Import Git Repository"로 이 저장소 연결
3. 프로젝트 설정의 Environment Variables에 `DART_API_KEY` 등록 (절대 코드/레포에 직접 넣지 않음)
4. 배포 완료 후 발급되는 `*.vercel.app` 주소로 접속

`vercel.json`이 `api/index.py`(Flask 앱)를 단일 서버리스 함수로 라우팅하도록 설정되어 있습니다. Vercel 환경에서는 `corpCode.xml` 캐시가 `/tmp`에 저장되며, 콜드 스타트 시 재다운로드될 수 있습니다.

## 한계사항

- 연결재무제표(CFS) + 사업보고서(연간) 기준으로만 조회합니다. 별도재무제표나 분기/반기 보고서는 지원하지 않습니다.
- 기본 연도 로직은 12월 결산법인을 기준으로 합니다. 결산월이 다른 회사는 `--years` 옵션으로 직접 연도를 지정하세요.
- 계정명은 회사마다 표기가 달라질 수 있어 XBRL 표준 계정ID(`account_id`) 매칭을 우선하고, 실패 시 계정명 별칭으로 재시도합니다. 금융업·지주사 등 특수한 계정체계를 쓰는 회사는 일부 항목이 "N/A"로 표시될 수 있습니다.
- 신설법인 등으로 특정 연도 데이터가 없으면 해당 항목은 "N/A"로 표시되고, 실행 종료 시 콘솔에 경고 목록이 출력됩니다.

## 프로젝트 구조

```
dart_lib/
  config.py          # .env 로드, 상수 정의 (Vercel 환경 캐시 경로 분기 포함)
  corp_code.py        # corpCode.xml 다운로드/캐싱/파싱, 회사명 검색
  dart_client.py       # DART 재무제표 API 호출 (재시도/에러 처리)
  account_map.py       # 계정 매칭(account_id 우선 + alias fallback), 재무비율 계산
  excel_writer.py       # openpyxl 워크북 생성 (파일 저장 / 메모리 바이트 반환 겸용)
  pipeline.py           # 연도 결정, 3사×N개년 조회 오케스트레이션 (CLI/웹 공용)
api/
  index.py             # Flask 웹 앱 (Vercel 진입점)
  templates/index.html   # 검색+비교 폼, 결과 테이블
  static/style.css
main.py             # CLI 진입점
vercel.json          # Vercel 배포 설정
cache/               # corpCode.xml 캐시 (자동 생성, 로컬 전용)
output/              # CLI 결과 엑셀 저장 위치 (자동 생성)
```
