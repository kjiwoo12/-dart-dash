import argparse
import sys
from datetime import datetime

if sys.platform == "win32":
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dart_lib import config, corp_code, excel_writer
from dart_lib.pipeline import collect_results, resolve_years


def parse_args():
    parser = argparse.ArgumentParser(description="DART 재무제표 비교 분석기")
    parser.add_argument(
        "--years",
        type=str,
        default=None,
        help="비교할 사업연도 (쉼표 구분, 예: 2022,2023,2024). 생략 시 최근 확정된 3개년 자동 사용",
    )
    return parser.parse_args()


def prompt_companies(corp_list: list[dict]) -> list[dict]:
    resolved = []
    print("비교할 회사 3곳의 이름을 입력하세요.")
    for i in range(1, 4):
        while True:
            name = input(f"  {i}번째 회사명: ").strip()
            if not name:
                print("  회사명을 입력해주세요.")
                continue
            company = corp_code.resolve_company_interactive(name, corp_list)
            if company is None:
                continue
            resolved.append(company)
            print(f"  -> 선택됨: {company['corp_name']} (corp_code={company['corp_code']})")
            break
    return resolved


def main():
    args = parse_args()
    try:
        years = resolve_years(args.years)
    except ValueError as exc:
        raise SystemExit(f"[오류] {exc}")

    print(f"비교 연도: {', '.join(years)}년")
    print("DART 고유번호 목록을 확인하는 중...")
    corp_list = corp_code.load_corp_list()
    print(f"전체 회사 수: {len(corp_list)}")

    companies = prompt_companies(corp_list)
    company_names = [c["corp_name"] for c in companies]

    print()
    print("재무제표를 조회하는 중입니다...")
    results, warnings = collect_results(companies, years)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{config.OUTPUT_DIR}/재무분석_{timestamp}.xlsx"
    excel_writer.write_workbook(results, company_names, years, output_path)

    print(f"완료: {output_path} 에 저장되었습니다.")

    if warnings:
        print()
        print(f"[경고] {len(warnings)}건의 주의사항이 있습니다:")
        for w in warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
