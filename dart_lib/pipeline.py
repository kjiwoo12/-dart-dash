from concurrent.futures import ThreadPoolExecutor
from datetime import date

from dart_lib import account_map, dart_client


def default_years() -> list[str]:
    today = date.today()
    last_confirmed = today.year - 1 if today.month >= 4 else today.year - 2
    return [str(last_confirmed - 2), str(last_confirmed - 1), str(last_confirmed)]


def resolve_years(years_arg: str | None) -> list[str]:
    """쉼표로 구분된 연도 문자열(예: "2022,2023,2024")을 받아 목록으로 변환한다.
    비어있으면 최근 확정된 3개년을 기본값으로 사용한다.
    """
    if years_arg:
        years = [y.strip() for y in years_arg.split(",") if y.strip()]
        if not years:
            raise ValueError("--years 형식이 올바르지 않습니다. 예: 2022,2023,2024")
        return years
    return default_years()


def _fetch_one(company: dict, year: str):
    name = company["corp_name"]
    corp_code_value = company["corp_code"]

    try:
        rows = dart_client.fetch_financial_statements(corp_code_value, year)
    except dart_client.DartAPIError as exc:
        return name, year, {}, f"{name} {year}년: API 오류 - {exc}"

    if not rows:
        return name, year, {}, f"{name} {year}년: 조회된 재무제표 데이터 없음 (신설법인 등)"

    metrics = account_map.extract_all_metrics(rows)
    ratios = account_map.compute_ratios(metrics)

    missing = [k for k, v in metrics.items() if v is None]
    warning = f"{name} {year}년: 매칭 실패 항목 - {', '.join(missing)}" if missing else None

    return name, year, {**metrics, **ratios}, warning


def collect_results(companies: list[dict], years: list[str]):
    """companies: [{"corp_name": ..., "corp_code": ...}, ...]

    반환: (results, warnings)
    results: {회사명: {연도: {지표명: 값}}}

    DART API 호출은 회사×연도 조합마다 독립적이므로 병렬로 처리해
    서버리스 환경의 실행시간 제한 내에 끝나도록 한다.
    """
    results = {c["corp_name"]: {} for c in companies}
    warnings = []
    tasks = [(company, year) for company in companies for year in years]

    with ThreadPoolExecutor(max_workers=min(9, len(tasks) or 1)) as executor:
        futures = [executor.submit(_fetch_one, company, year) for company, year in tasks]
        for future in futures:
            name, year, data, warning = future.result()
            results[name][year] = data
            if warning:
                warnings.append(warning)

    return results, warnings
