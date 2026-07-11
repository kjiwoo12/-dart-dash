import os
import sys
from datetime import datetime
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, render_template, request, Response

from dart_lib import corp_code
from dart_lib.excel_writer import ALL_ROW_LABELS, RATIO_METRICS, build_workbook, workbook_to_bytes
from dart_lib.pipeline import collect_results, resolve_years

_UNIT_DIVISOR = 1_000_000  # 화면 표시는 백만원 단위 (엑셀 다운로드는 원 단위 그대로 유지)


def _to_display_results(results):
    display = {}
    for company, by_year in results.items():
        display[company] = {}
        for year, metrics in by_year.items():
            display[company][year] = {
                label: (
                    value
                    if value is None or label in RATIO_METRICS
                    else round(value / _UNIT_DIVISOR)
                )
                for label, value in metrics.items()
            }
    return display

app = Flask(__name__)

_CORP_LIST_CACHE = {"data": None}


def _get_corp_list():
    if _CORP_LIST_CACHE["data"] is None:
        _CORP_LIST_CACHE["data"] = corp_code.load_corp_list()
    return _CORP_LIST_CACHE["data"]


def _resolve_company(corp_list, name_raw, code_raw):
    """자동완성으로 선택된 corp_code가 있으면 그대로 사용하고,
    없으면 이름으로 검색해 정확히 1건일 때만 확정한다.
    반환: (company_dict | None, error_message | None)
    """
    name_raw = (name_raw or "").strip()
    code_raw = (code_raw or "").strip()

    if code_raw:
        match = next((c for c in corp_list if c["corp_code"] == code_raw), None)
        if match:
            return match, None

    if not name_raw:
        return None, "회사명을 입력해주세요."

    unique = corp_code.resolve_unique_company(name_raw, corp_list)
    if unique:
        return unique, None

    matches = corp_code.search_company(name_raw, corp_list)
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, f'"{name_raw}"에 해당하는 회사를 찾을 수 없습니다.'
    return None, f'"{name_raw}"에 해당하는 후보가 여러 개입니다. 자동완성 목록에서 선택해주세요.'


def _resolve_form(form, corp_list):
    """폼 데이터에서 3개 회사 + 연도를 확정한다. 반환: (companies, years, error)"""
    companies = []
    for i in (1, 2, 3):
        company, err = _resolve_company(
            corp_list, form.get(f"company{i}_name"), form.get(f"company{i}_code")
        )
        if err:
            return None, None, f"{i}번째 회사: {err}"
        companies.append(company)

    try:
        years = resolve_years(form.get("years"))
    except ValueError as exc:
        return None, None, str(exc)

    return companies, years, None


@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html", results=None, warnings=None, error=None, form_values={}, metric_labels=ALL_ROW_LABELS
    )


@app.route("/api/search", methods=["GET"])
def api_search():
    q = request.args.get("q", "")
    corp_list = _get_corp_list()
    matches = corp_code.search_company(q, corp_list)[:20]
    return jsonify(
        [
            {"name": m["corp_name"], "corp_code": m["corp_code"], "stock_code": m["stock_code"]}
            for m in matches
        ]
    )


@app.route("/compare", methods=["POST"])
def compare():
    corp_list = _get_corp_list()
    companies, years, error = _resolve_form(request.form, corp_list)

    form_values = request.form.to_dict()

    if error:
        return render_template(
            "index.html", results=None, warnings=None, error=error, form_values=form_values,
            metric_labels=ALL_ROW_LABELS,
        )

    company_names = [c["corp_name"] for c in companies]
    results, warnings = collect_results(companies, years)

    # 다운로드 폼에 그대로 넘겨줄 확정된 값들
    for i, c in enumerate(companies, start=1):
        form_values[f"company{i}_name"] = c["corp_name"]
        form_values[f"company{i}_code"] = c["corp_code"]
    form_values["years"] = ",".join(years)

    return render_template(
        "index.html",
        results=_to_display_results(results),
        companies=company_names,
        years=years,
        warnings=warnings,
        error=None,
        form_values=form_values,
        metric_labels=ALL_ROW_LABELS,
    )


@app.route("/download", methods=["POST"])
def download():
    corp_list = _get_corp_list()
    companies, years, error = _resolve_form(request.form, corp_list)
    if error:
        return error, 400

    company_names = [c["corp_name"] for c in companies]
    results, _warnings = collect_results(companies, years)

    wb = build_workbook(results, company_names, years)
    data = workbook_to_bytes(wb)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"재무분석_{timestamp}.xlsx"
    filename_encoded = quote(filename)

    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"dart_analysis_{timestamp}.xlsx\"; "
                f"filename*=UTF-8''{filename_encoded}"
            )
        },
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
