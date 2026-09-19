import enum


class DocType(enum.StrEnum):
    EARNINGS_CALL = "earnings_call"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ClaimCategory(enum.StrEnum):
    REVENUE_GROWTH = "revenue_growth"
    MARGIN_EXPANSION = "margin_expansion"
    CAPEX = "capex"
    DEBT_REDUCTION = "debt_reduction"
    MARKET_SHARE = "market_share"
    NEW_PRODUCTS = "new_products"
    COST_OPTIMIZATION = "cost_optimization"
    EMPLOYEE_GROWTH = "employee_growth"
    GEOGRAPHIC_EXPANSION = "geographic_expansion"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
