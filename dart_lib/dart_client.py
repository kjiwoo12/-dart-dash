import time

import requests

from dart_lib import config


class DartAPIError(Exception):
    pass


# 정상 처리 흐름으로 취급하는 상태코드 (예외적 사업연도 등)
_NO_DATA_STATUS = {"013"}


def fetch_financial_statements(
    corp_code: str,
    bsns_year: str,
    reprt_code: str = config.REPRT_CODE_ANNUAL,
    fs_div: str = config.FS_DIV_CONSOLIDATED,
    retries: int = 2,
) -> list[dict]:
    """단일회사 전체 재무제표를 조회한다.

    status=013(조회된 데이터 없음)은 예외가 아닌 정상 케이스로 보고 빈 리스트를 반환한다.
    """
    params = {
        "crtfc_key": config.DART_API_KEY,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
        "fs_div": fs_div,
    }

    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                f"{config.BASE_URL}/fnlttSinglAcntAll.json", params=params, timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
            continue

        status = data.get("status")

        if status == "000":
            time.sleep(0.2)  # API 매너 딜레이
            return data.get("list", [])

        if status in _NO_DATA_STATUS:
            return []

        if status == "020":  # 요청 제한 초과 -> 백오프 후 재시도
            last_error = DartAPIError(f"요청 제한 초과: {data.get('message')}")
            time.sleep(1.0 * (attempt + 1))
            continue

        # 그 외 에러(100=파라미터오류, 800=시스템점검 등)는 즉시 실패
        raise DartAPIError(
            f"DART API 오류 (status={status}): {data.get('message')} "
            f"(corp_code={corp_code}, bsns_year={bsns_year})"
        )

    raise DartAPIError(
        f"DART API 호출 재시도 초과 (corp_code={corp_code}, bsns_year={bsns_year}): {last_error}"
    )


if __name__ == "__main__":
    # 삼성전자(corp_code=00126380) 2023 사업연도 연결재무제표 조회 테스트
    rows = fetch_financial_statements("00126380", "2023")
    print(f"row count: {len(rows)}")
    for r in rows[:5]:
        print(r.get("sj_div"), r.get("account_id"), r.get("account_nm"), r.get("thstrm_amount"))
