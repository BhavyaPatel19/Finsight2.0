import enum


class DocType(str, enum.Enum):
    EARNINGS_CALL = "earnings_call"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ClaimCategory(str, enum.Enum):
    REVENUE_GROWTH = "revenue_growth"
    MARGIN_EXPANSION = "margin_expansion"
    DEBT_REDUCTION = "debt_reduction"
    MARKET_EXPANSION = "market_expansion"
