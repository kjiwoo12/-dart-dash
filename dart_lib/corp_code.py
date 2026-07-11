import gzip
import io
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

import requests

from dart_lib import config

if sys.platform == "win32":
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 매 요청마다 DART에서 30MB짜리 corpCode.xml을 새로 받는 것은 서버리스 환경(Vercel)에서
# 콜드 스타트 시간제한을 넘기므로, 미리 정제해 저장소에 포함한 스냅샷을 기본으로 사용한다.
# 최신 상장/신설 정보가 필요하면 아래 refresh_bundled_corp_list()로 주기적으로 재생성한다.
_BUNDLED_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "corp_code.json.gz")


def ensure_corp_code_cache(force: bool = False) -> str:
    """corpCode.xml 캐시를 보장하고 경로를 반환한다. 없거나 오래되었으면 새로 받는다."""
    path = config.CORP_CODE_CACHE_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if not force and os.path.exists(path):
        age_days = (time.time() - os.path.getmtime(path)) / 86400
        if age_days <= config.CORP_CODE_CACHE_MAX_AGE_DAYS:
            return path

    resp = requests.get(
        f"{config.BASE_URL}/corpCode.xml",
        params={"crtfc_key": config.DART_API_KEY},
        timeout=30,
    )
    resp.raise_for_status()

    if not zipfile.is_zipfile(io.BytesIO(resp.content)):
        raise RuntimeError(
            "[오류] corpCode.xml 다운로드에 실패했습니다. "
            f"DART API 키가 올바른지 확인해주세요. 응답 내용: {resp.text[:300]}"
        )

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        data = zf.read("CORPCODE.xml")

    with open(path, "wb") as f:
        f.write(data)

    return path


def _parse_corp_code_xml(path: str) -> list[dict]:
    tree = ET.parse(path)
    root = tree.getroot()

    corp_list = []
    for item in root.findall("list"):
        corp_list.append(
            {
                "corp_code": (item.findtext("corp_code") or "").strip(),
                "corp_name": (item.findtext("corp_name") or "").strip(),
                "stock_code": (item.findtext("stock_code") or "").strip(),
                "modify_date": (item.findtext("modify_date") or "").strip(),
            }
        )
    return corp_list


def load_corp_list() -> list[dict]:
    """회사 목록을 반환한다. 저장소에 번들된 스냅샷이 있으면 그것을 우선 사용하고
    (네트워크 호출 없이 즉시 로드), 없으면 DART에서 corpCode.xml을 받아 파싱한다.
    """
    if os.path.exists(_BUNDLED_DATA_PATH):
        with gzip.open(_BUNDLED_DATA_PATH, "rt", encoding="utf-8") as f:
            records = json.load(f)
        return [
            {"corp_code": r[0], "corp_name": r[1], "stock_code": r[2], "modify_date": r[3]}
            for r in records
        ]

    path = ensure_corp_code_cache()
    return _parse_corp_code_xml(path)


def refresh_bundled_corp_list() -> str:
    """DART에서 최신 corpCode.xml을 받아 번들 스냅샷(dart_lib/data/corp_code.json.gz)을
    재생성한다. 신규 상장/신설 법인을 반영하려면 주기적으로 실행 후 커밋한다.
    """
    path = ensure_corp_code_cache(force=True)
    corp_list = _parse_corp_code_xml(path)

    records = [
        [c["corp_code"], c["corp_name"], c["stock_code"], c["modify_date"]] for c in corp_list
    ]
    os.makedirs(os.path.dirname(_BUNDLED_DATA_PATH), exist_ok=True)
    data = json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.open(_BUNDLED_DATA_PATH, "wb", compresslevel=9) as f:
        f.write(data)

    return _BUNDLED_DATA_PATH


def _normalize(name: str) -> str:
    return name.strip().replace(" ", "").lower()


def search_company(name: str, corp_list: list[dict]) -> list[dict]:
    """이름으로 회사를 검색한다. 완전일치 우선, 그다음 부분일치. 상장사 우선 정렬."""
    target = _normalize(name)
    if not target:
        return []

    exact = [c for c in corp_list if _normalize(c["corp_name"]) == target]
    if exact:
        matches = exact
    else:
        matches = [c for c in corp_list if target in _normalize(c["corp_name"])]

    matches.sort(key=lambda c: (c["stock_code"] == "", c["corp_name"]))
    return matches


def resolve_company_interactive(name: str, corp_list: list[dict]) -> dict | None:
    """이름으로 회사를 검색해 사용자와 상호작용으로 하나를 확정한다."""
    while True:
        matches = search_company(name, corp_list)

        if len(matches) == 1:
            return matches[0]

        if not matches:
            print(f'  "{name}"에 해당하는 회사를 찾을 수 없습니다.')
            name = input("  회사명을 다시 입력하세요 (건너뛰려면 빈 값 입력): ").strip()
            if not name:
                return None
            continue

        display = matches[:15]
        print(f'  "{name}"에 해당하는 후보가 {len(matches)}개 있습니다:')
        for i, c in enumerate(display, start=1):
            market = "상장" if c["stock_code"] else "비상장"
            print(f"   {i}. {c['corp_name']} ({market}, corp_code={c['corp_code']})")
        choice = input(f"  번호를 선택하세요 (1-{len(display)}): ").strip()

        if choice.isdigit() and 1 <= int(choice) <= len(display):
            return display[int(choice) - 1]

        print("  잘못된 입력입니다. 다시 시도합니다.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--refresh":
        path = refresh_bundled_corp_list()
        print(f"번들 스냅샷 갱신 완료: {path}")
    else:
        corp_list = load_corp_list()
        print(f"전체 회사 수: {len(corp_list)}")
        test_name = input("검색할 회사명을 입력하세요 (예: 삼성전자): ").strip()
        result = resolve_company_interactive(test_name, corp_list)
        print("선택된 회사:", result)
