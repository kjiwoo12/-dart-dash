import re

# 항목명 -> {sj_div(재무제표구분) 허용목록, account_id(XBRL) 우선매칭, account_nm alias fallback}
TARGET_METRICS = {
    "자산총계": {
        "sj_div": ["BS"],
        "account_ids": ["ifrs-full_Assets"],
        "aliases": ["자산총계"],
    },
    "부채총계": {
        "sj_div": ["BS"],
        "account_ids": ["ifrs-full_Liabilities"],
        "aliases": ["부채총계"],
    },
    "자본총계": {
        "sj_div": ["BS"],
        "account_ids": ["ifrs-full_Equity"],
        "aliases": ["자본총계"],
    },
    "매출액": {
        "sj_div": ["IS", "CIS"],
        "account_ids": ["ifrs-full_Revenue", "ifrs-full_RevenueFromContractsWithCustomers"],
        "aliases": ["매출액", "수익(매출액)", "영업수익"],
    },
    "영업이익": {
        "sj_div": ["IS", "CIS"],
        "account_ids": ["dart_OperatingIncomeLoss"],
        "aliases": ["영업이익", "영업이익(손실)"],
    },
    "당기순이익": {
        "sj_div": ["IS", "CIS"],
        "account_ids": ["ifrs-full_ProfitLoss"],
        "aliases": ["당기순이익", "당기순이익(손실)"],
    },
    "영업활동현금흐름": {
        "sj_div": ["CF"],
        "account_ids": ["ifrs-full_CashFlowsFromUsedInOperatingActivities"],
        "aliases": ["영업활동으로 인한 현금흐름", "영업활동현금흐름"],
    },
    "투자활동현금흐름": {
        "sj_div": ["CF"],
        "account_ids": ["ifrs-full_CashFlowsFromUsedInInvestingActivities"],
        "aliases": ["투자활동으로 인한 현금흐름", "투자활동현금흐름"],
    },
    "재무활동현금흐름": {
        "sj_div": ["CF"],
        "account_ids": ["ifrs-full_CashFlowsFromUsedInFinancingActivities"],
        "aliases": ["재무활동으로 인한 현금흐름", "재무활동현금흐름"],
    },
}

METRIC_ORDER = list(TARGET_METRICS.keys())


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def parse_amount(raw) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "")
    if not text or text == "-":
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def extract_metric(rows: list[dict], metric_key: str) -> int | None:
    spec = TARGET_METRICS[metric_key]
    candidates = [r for r in rows if r.get("sj_div") in spec["sj_div"]]

    # 1순위: account_id 정확 매칭
    for r in candidates:
        if r.get("account_id") in spec["account_ids"]:
            value = parse_amount(r.get("thstrm_amount"))
            if value is not None:
                return value

    # 2순위: account_nm 정규화 후 alias 매칭
    alias_set = {normalize(a) for a in spec["aliases"]}
    for r in candidates:
        if normalize(r.get("account_nm")) in alias_set:
            value = parse_amount(r.get("thstrm_amount"))
            if value is not None:
                return value

    return None


def extract_all_metrics(rows: list[dict]) -> dict[str, int | None]:
    return {key: extract_metric(rows, key) for key in METRIC_ORDER}


def compute_ratios(metrics: dict[str, int | None]) -> dict[str, float | None]:
    equity = metrics.get("자본총계")
    liabilities = metrics.get("부채총계")
    net_income = metrics.get("당기순이익")

    roe = None
    if equity not in (None, 0) and net_income is not None:
        roe = round(net_income / equity * 100, 2)

    debt_ratio = None
    if equity not in (None, 0) and liabilities is not None:
        debt_ratio = round(liabilities / equity * 100, 2)

    return {"ROE(%)": roe, "부채비율(%)": debt_ratio}


if __name__ == "__main__":
    from dart_lib import dart_client

    rows = dart_client.fetch_financial_statements("00126380", "2023")
    metrics = extract_all_metrics(rows)
    for k, v in metrics.items():
        print(k, ":", v)
    ratios = compute_ratios(metrics)
    for k, v in ratios.items():
        print(k, ":", v)
