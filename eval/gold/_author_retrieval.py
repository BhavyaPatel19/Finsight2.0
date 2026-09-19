"""
Authoring source for eval/gold/retrieval.jsonl.

Each item: question, reference answer, the document(s) that answer it, and
one or more verbatim evidence quotes. `python -m eval.gold._author_retrieval`
validates every quote against the extracted document text, resolves the
page(s) that contain it, and writes retrieval.jsonl. Items whose evidence
cannot be found fail loudly — a gold set must not drift from its sources.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "retrieval.jsonl"

C25, P25, F25 = "INFY_concall_Q4FY25", "INFY_press_Q4FY25", "INFY_factsheet_Q4FY25"
C1_26 = "INFY_concall_Q1FY26"
C26, P26, F26 = "INFY_concall_Q4FY26", "INFY_press_Q4FY26", "INFY_factsheet_Q4FY26"
C1_27 = "INFY_concall_Q1FY27"

ITEMS: list[dict] = [
    # ---------------- Q4 FY25 earnings call (April 2025) ----------------
    dict(q="What revenue growth guidance did Infosys give for FY26 on the Q4 FY25 call?",
         a="0% to 3% growth in constant currency terms.", type="guidance",
         ev={C25: ["our guidance for growth for financial year '26 is 0% to 3% in constant currency terms"],
             P25: ["FY26 revenue guidance at 0%-3%", "Revenue growth of 0%-3% in constant currency"]}),
    dict(q="What operating margin guidance did Infosys give for FY26 in April 2025?",
         a="20% to 22%.", type="guidance",
         ev={C25: ["Our margin guidance for financial year 2026 is 20% to 22%"],
             P25: ["operating margin at 20%-22%"]}),
    dict(q="What was Infosys's FY25 revenue in US dollars and its constant-currency growth?",
         a="$19.3 bn, growth of 4.2% in constant currency (3.9% reported).", type="numeric",
         ev={C25: ["We closed the year with revenues at $19.3 bn, a growth of 4.2% in constant currency terms and 3.9% in reported terms"],
             P25: ["delivered $19,277 million in FY25 revenues, growth of 4.2% in constant currency"]}),
    dict(q="How much did acquisitions contribute to Infosys's FY25 growth?",
         a="80 basis points.", type="numeric",
         ev={C25: ["Acquisitions contributed 80 basis points to the growth in financial year '25"]}),
    dict(q="What was Infosys's operating margin for FY25 and how much did it improve over FY24?",
         a="21.1%, an improvement of 50 basis points over FY24.", type="numeric",
         ev={C25: ["operating margins for the financial year improved 50 basis points over FY'24 to 21.1%"],
             P25: ["Operating margin was at 21.1%, expansion of 0.5% year on year"]}),
    dict(q="What was Infosys's free cash flow in FY25, and what percentage of net profit was it?",
         a="$4.1 bn, the highest ever, at 129% of net profit.", type="numeric",
         ev={C25: ["Free cash flow for FY'25 was highest ever at $4.1 bn, 129% of net profit", "FY'25 free cash flows are highest ever at $4.1 bn"]}),
    dict(q="How many large deals did Infosys close in FY25 and what was their total contract value?",
         a="96 deals with TCV of $11.6 bn, 56% net new.", type="numeric",
         ev={C25: ["For the full year, we closed 96 deals with TCV of $11.6 bn and 56% net new"]}),
    dict(q="How many large deals did Infosys sign in Q4 FY25 and what share was net new?",
         a="24 large deals with TCV of $2.6 bn; 63% net new.", type="numeric",
         ev={C25: ["We closed 24 large deals in Q4 with a TCV of $2.6 bn, 63% of this was net new"]}),
    dict(q="How fast did Europe grow for Infosys in Q4 FY25 and what share of revenue does it represent?",
         a="Europe grew 15% in constant currency (3x the company rate) and is 30% of revenues.", type="numeric",
         ev={C25: ["Europe grew 3x of the company rate at 15% in constant currency terms", "Europe now accounts for 30% of our revenues"]}),
    dict(q="Which Infosys verticals grew double digit year-on-year in Q4 FY25, and by how much?",
         a="Financial Services grew 12.6% and Manufacturing 14% in constant currency.", type="numeric",
         ev={C25: ["Financial Services and Manufacturing grew double digit year-on-year at 12.6% and 14%, respectively"]}),
    dict(q="What was Infosys's headcount at the end of FY25 and its attrition rate?",
         a="323,578 employees (up ~6,000 YoY); attrition 14.1%.", type="numeric",
         ev={C25: ["Headcount at the end of the year was 323,578, an increase of ~6,000 year-on-year", "Attrition remained contained at 14.1%"],
             F25: ["Total employees | 323,578 | 323,379 | 317,240"]}),
    dict(q="How many freshers did Infosys hire in FY25 and how many does it plan to hire in FY26?",
         a="15,000 in FY25; over 20,000 planned for FY26.", type="guidance",
         ev={C25: ["We hired 15,000 freshers this year and expect to hire over 20,000 freshers in FY'26"]}),
    dict(q="What effective tax rate does Infosys expect for FY26?",
         a="29% to 30%.", type="guidance",
         ev={C25: ["We expect effective tax rate for financial year '26 to be in the range of 29% to 30%"],
             C1_26: ["We expect the effective ETR rate for the financial year'26 to be in the range of 29% to 30%"]}),
    dict(q="What was Infosys's consolidated cash position and ROE at the end of FY25?",
         a="Cash and cash equivalents of $5.56 bn; ROE of 29%.", type="numeric",
         ev={C25: ["Consolidated cash and cash equivalents stood at $5.56 bn at the end of the year", "ROE stood at 29%"]}),
    dict(q="Why did Infosys revenue decline sequentially in Q4 FY25?",
         a="Revenue fell 3.5% in constant currency due to reduced third-party costs and seasonal weakness; about two-thirds of the decline was third-party related.", type="explanatory",
         ev={C25: ["revenue declined by 3.5% in constant currency terms due to reduction in third-party costs and seasonal weakness"]}),
    dict(q="When do Infosys employees receive wage hikes according to the Q4 FY25 call?",
         a="Most employees got hikes in January; middle to senior level employees effective 1 April.", type="factual",
         ev={C25: ["most of our employees got the wage hikes in January and the middle level to senior level employees will get wage hike, effective 1st of April"]}),
    dict(q="What margin headwind did Infosys attribute to M&A-related costs in FY25?",
         a="About 40 basis points, described as one-off.", type="numeric",
         ev={C25: ["The 40 bps of charge that we took on related to the acquisition is one-off in a way"]}),
    dict(q="What is Infosys's expectation for FY26 free cash flow relative to net profit?",
         a="Above 100% of net profit.", type="guidance",
         ev={C25: ["We expect FY'26 free cash flows to be above 100% of net profit"],
             C1_26: ["We expect FY26 free cash flows to be above 100% of net profit"]}),

    # ---------------- Q4 FY25 press release ----------------
    dict(q="What were Infosys's Q4 FY25 revenues in dollars and the year-on-year growth?",
         a="$4,730 million, up 4.8% YoY in constant currency and 3.6% in reported terms.", type="numeric",
         ev={P25: ["Q4 revenues were $4,730 million, an increase of 4.8% year on year in constant currency and 3.6% in reported terms"],
             F25: ["Revenues | 4,730 | 4,564 | 3.6%"]}),
    dict(q="What was Infosys's Q4 FY25 operating margin according to the press release?",
         a="21.0%, an increase of 0.9% year on year.", type="numeric",
         ev={P25: ["Operating margin was at 21.0%, an increase of 0.9% year on year"],
             F25: ["Operating Margin % | 21.0 | 20.1 | 0.9%"]}),
    dict(q="For how many consecutive years has Infosys been named one of the World's Most Ethical Companies by Ethisphere, as of 2025?",
         a="Five consecutive years.", type="factual",
         ev={P25: ["Recognized as one of the World’s Most Ethical Companies in 2025 for the fifth consecutive year by Ethisphere"]}),
    dict(q="What were Infosys's cash and cash equivalents on the balance sheet at March 31, 2025 versus March 31, 2024?",
         a="$2,861 million vs $1,773 million.", type="numeric",
         ev={P25: ["Cash and cash equivalents | 2,861 | 1,773"]}),

    # ---------------- Q4 FY25 fact sheet ----------------
    dict(q="What share of Infosys revenue came from Financial Services in Q4 FY25?",
         a="28.4%.", type="numeric",
         ev={F25: ["Financial services | 28.4 | 27.8 | 26.4"]}),
    dict(q="What share of Infosys revenue came from North America and Europe in Q4 FY25?",
         a="North America 57.1%, Europe 31.2%.", type="numeric",
         ev={F25: ["North America | 57.1 | 58.4 | 59.6", "Europe | 31.2 | 29.8 | 28.6"]}),
    dict(q="What was Infosys's total employee count at March 31, 2025, December 31, 2024 and March 31, 2024?",
         a="323,578; 323,379; 317,240.", type="numeric",
         ev={F25: ["Total employees | 323,578 | 323,379 | 317,240"]}),
    dict(q="What was Infosys's voluntary attrition (LTM, IT services) at the end of Q4 FY25 and a year earlier?",
         a="14.1% vs 12.6%.", type="numeric",
         ev={F25: ["Voluntary Attrition % (LTM - IT Services) | 14.1% | 13.7% | 12.6%"]}),
    dict(q="What was Infosys's Q4 FY25 gross profit in US dollars?",
         a="$1,428 million (vs $1,345 million a year earlier).", type="numeric",
         ev={F25: ["Gross Profit | 1,428 | 1,345"]}),
    dict(q="What dividend per share did Infosys declare for FY25 in rupees, and how does it compare with FY24?",
         a="Rs 43.00 vs Rs 38.00, up 13.2%.", type="numeric",
         ev={F25: ["Dividend Per Share ( ) (3) | 43.00 | 38.00 | 13.2%"]}),
    dict(q="What percentage of Infosys revenue came from its top 10 clients in Q4 FY25?",
         a="20.7%.", type="numeric",
         ev={F25: ["Top 10 clients | 20.7% | 19.9% | 20.4%"]}),
    dict(q="What USD/INR exchange rate was used for Q4 FY25 in the fact sheet?",
         a="86.10.", type="numeric",
         ev={F25: ["USD/INR exchange rate of 86.10 considered for Q4’25"]}),

    # ---------------- Q1 FY26 earnings call (July 2025) ----------------
    dict(q="How did Infosys change its FY26 revenue guidance on the Q1 FY26 call?",
         a="Raised from 0%–3% to 1%–3% growth in constant currency; margin guidance unchanged at 20%–22%.", type="guidance",
         ev={C1_26: ["From the earlier guidance of 0% to 3%, now it is 1% to 3% growth in constant currency terms"]}),
    dict(q="What were Infosys's sequential and year-on-year constant-currency growth rates in Q1 FY26?",
         a="2.6% sequentially and 3.8% year-on-year.", type="numeric",
         ev={C1_26: ["Our revenues grew 2.6% sequentially and 3.8% year-on-year in constant currency terms"]}),
    dict(q="What was Infosys's free cash flow in Q1 FY26 and how did it compare with net profit?",
         a="$884 mn, 109% of net profit — the fifth consecutive quarter above 100%.", type="numeric",
         ev={C1_26: ["free cash flows of $884 mn, which is 109% of net profit"]}),
    dict(q="What was Infosys's operating margin in Q1 FY26 and how did it move?",
         a="20.8%, down 20 bps QoQ and 30 bps YoY.", type="numeric",
         ev={C1_26: ["Operating margins were at 20.8%, down 20 basis points QoQ and 30 basis points year-on-year"]}),
    dict(q="How much did third-party costs fall in Q1 FY26, as a share of revenue?",
         a="Down 60 basis points to 7.3% of revenue.", type="numeric",
         ev={C1_26: ["significant reduction in third-party costs by 60 basis points to 7.3% of revenue"]}),
    dict(q="How fast did Europe grow year-on-year for Infosys in Q1 FY26?",
         a="12.3%, over 3x the company average.", type="numeric",
         ev={C1_26: ["Europe grew 12.3%, which is over 3x the company average"]}),
    dict(q="What was Infosys's utilization excluding trainees in Q1 FY26?",
         a="85.2%, up 30 basis points QoQ.", type="numeric",
         ev={C1_26: ["Utilization, excluding trainees, went up 30 basis points QoQ at 85.2%"]}),

    # ---------------- Q4 FY26 earnings call (April 2026) ----------------
    dict(q="What was Infosys's full-year FY26 constant-currency revenue growth?",
         a="3.1%.", type="numeric",
         ev={C26: ["We had a growth of 3.1% for the full year in constant currency terms", "FY26 revenues crossed $20 bn and grew 3.1% in constant currency terms"],
             P26: ["growth of 3.1% in FY 26 in constant currency", "delivered $20,158 million in FY 26 revenues with a growth of 3.1% in constant currency"]}),
    dict(q="What revenue growth guidance did Infosys give for FY27 in April 2026?",
         a="1.5% to 3.5% year-on-year in constant currency; operating margin 20%–22%.", type="guidance",
         ev={C26: ["Our revenue growth guidance of financial year '27 is 1.5% to 3.5% year-on-year in constant currency terms"],
             P26: ["FY 27 Guidance – Revenue Growth of 1.5%-3.5%, Operating Margin of 20%-22%", "Revenue growth of 1.5%-3.5% in constant currency"]}),
    dict(q="How many large deals did Infosys sign in FY26 and what was the TCV?",
         a="96 large deals with TCV of $15 bn (press release: $14.9 bn), 55% net new.", type="numeric",
         ev={C26: ["In FY26, we signed 96 large deals with TCV of $15 bn, 55% net new", "For the full year, we had $14.9 bn of large deals"],
             P26: ["Strong Large Deal wins of $14.9 Billion"]}),
    dict(q="What was Infosys's ROE at the end of FY26?",
         a="31.6%.", type="numeric",
         ev={C26: ["ROE stood at 31.6%"]}),
    dict(q="How much did acquisitions contribute to Infosys's FY26 revenue growth?",
         a="About 70 basis points.", type="numeric",
         ev={C26: ["Acquisitions contributed about 70 bps on full year growth"]}),
    dict(q="Why did Infosys revenue decline sequentially in Q4 FY26?",
         a="Down 1.3% in constant currency due to seasonality and slower decision-making in March.", type="explanatory",
         ev={C26: ["revenues declined 1.3% in constant currency due to seasonality and slower decision making in the month of March"]}),
    dict(q="What was Infosys's onsite mix at the end of Q4 FY26?",
         a="22.8%, down from 23.1% in Q3.", type="numeric",
         ev={C26: ["Onsite mix further reduced to 22.8% from 23.1% in Q3"]}),
    dict(q="What annualized operating-margin impact does Infosys expect from the Optimum Healthcare, Stratus and Versent acquisitions?",
         a="Approximately 0.7% on a full-year annualized basis post closure.", type="guidance",
         ev={C26: ["The impact of Optimum Healthcare, Stratus and Versent on operating margin will be approximately 0.7%"]}),

    # ---------------- Q4 FY26 press release ----------------
    dict(q="What were Infosys's FY26 revenues in US dollars?",
         a="$20,158 million, crossing the $20 billion mark.", type="numeric",
         ev={P26: ["delivered $20,158 million in FY 26 revenues"],
             F26: ["Revenues | 20,158 | 19,277"]}),
    dict(q="What were Infosys's Q4 FY26 revenues and operating margin?",
         a="$5,040 million (4.1% YoY CC growth); operating margin 20.9%.", type="numeric",
         ev={P26: ["Q4 revenues were $5,040 million, growth of 4.1% year on year in constant currency. Q4 operating margin was at 20.9%"],
             F26: ["Revenues | 5,040 | 4,730 | 6.6%"]}),
    dict(q="What free cash flow did Infosys report for FY26?",
         a="$3.7 billion.", type="numeric",
         ev={P26: ["healthy Free Cash Flow of $3.7 Billion", "healthy free cash flow of $3.7 billion"]}),
    dict(q="What large deal wins did Infosys report for FY26 in the press release?",
         a="$14.9 billion.", type="numeric",
         ev={P26: ["Strong Large Deal wins of $14.9 Billion"],
             C26: ["For the full year, we had $14.9 bn of large deals"]}),

    # ---------------- Q4 FY26 fact sheet ----------------
    dict(q="What was Infosys's FY26 net profit after non-controlling interests in US dollars?",
         a="$3,313 million, up 4.9% from $3,158 million.", type="numeric",
         ev={F26: ["Net Profit (after non-controlling interests) | 3,313 | 3,158 | 4.9%"],
             P26: ["Net profit (after non-controlling interests) | 919 | 813 | 3,313 | 3,158"]}),
    dict(q="What was Infosys's total employee count at March 31, 2026?",
         a="328,594.", type="numeric",
         ev={F26: ["Total employees | 328,594 | 337,034 | 323,578"]}),
    dict(q="What dividend per share did Infosys declare for FY26 in rupees?",
         a="Rs 48.00, up 11.6% from Rs 43.00.", type="numeric",
         ev={F26: ["Dividend Per Share ( ) | 48.00 | 43.00 | 11.6%"]}),
    dict(q="What was Infosys's reported FY26 operating margin in the fact sheet?",
         a="20.3% (vs 21.1% in FY25).", type="numeric",
         ev={F26: ["Operating Margin % | 20.3 | 21.1 | -0.8%"]}),
    dict(q="What was Infosys's FY26 revenue in rupee crore?",
         a="Rs 178,650 crore, up 9.6%.", type="numeric",
         ev={F26: ["Revenues | 178,650 | 162,990 | 9.6%"]}),

    # ---------------- Q1 FY27 earnings call (July 2026) ----------------
    dict(q="What share of Infosys revenue came from AI services in Q1 FY27?",
         a="8.2% of overall revenue.", type="numeric",
         ev={C1_27: ["Our AI services revenue was 8.2% of overall revenue"]}),
    dict(q="How did Infosys revise its FY27 revenue guidance on the Q1 FY27 call?",
         a="Changed to 1.5% to 3% year-on-year growth in constant currency.", type="guidance",
         ev={C1_27: ["we have changed our revenue growth guidance to 1.5% to 3% Y-on-Y growth in constant currency terms"]}),
    dict(q="What were Infosys's large deal wins in Q1 FY27 and the net-new share?",
         a="$3.6 bn with 61% net new; 22 large deals including three worth $400 mn each.", type="numeric",
         ev={C1_27: ["Our large deals were $3.6 bn with a net new of 61%", "Out of the 22 large deal won, we had three deals worth $400 mn each"]}),
    dict(q="What was Infosys's Q1 FY27 revenue growth year-on-year and sequentially?",
         a="2.4% YoY and 1% QoQ in constant currency.", type="numeric",
         ev={C1_27: ["Our revenue growth for Q1 was 2.4% Y-on-Y and 1% Q-on-Q in constant currency terms"]}),
    dict(q="What was Infosys's free cash flow in Q1 FY27?",
         a="$955 mn.", type="numeric",
         ev={C1_27: ["Free cash flow at $955 mn"]}),
    dict(q="What share of Infosys's Q1 FY27 large deal TCV came from vendor consolidation?",
         a="About 20%.", type="numeric",
         ev={C1_27: ["20% of the total large deal TCV being from new vendor consolidation deals"]}),

    # ---------------- Cross-document (guidance vs outcome) ----------------
    dict(q="Infosys guided FY26 revenue growth of 0%–3% in April 2025. What growth did it actually deliver for FY26?",
         a="3.1% in constant currency — at the top of the original 0%–3% range.", type="cross_doc",
         ev={C25: ["our guidance for growth for financial year '26 is 0% to 3% in constant currency terms"],
             P25: ["FY26 revenue guidance at 0%-3%"],
             C26: ["We had a growth of 3.1% for the full year in constant currency terms"],
             P26: ["growth of 3.1% in FY 26 in constant currency"]}),
    dict(q="How did Infosys's FY26 revenue guidance evolve between April 2025 and July 2025?",
         a="From 0%–3% in April 2025 to 1%–3% in July 2025 (margin guidance unchanged at 20%–22%).", type="cross_doc",
         ev={C25: ["our guidance for growth for financial year '26 is 0% to 3% in constant currency terms"],
             C1_26: ["From the earlier guidance of 0% to 3%, now it is 1% to 3% growth in constant currency terms"]}),
    dict(q="How did Infosys's total headcount change between March 31, 2025 and March 31, 2026?",
         a="From 323,578 to 328,594 (+5,016).", type="cross_doc",
         ev={F25: ["Total employees | 323,578 | 323,379 | 317,240"],
             F26: ["Total employees | 328,594 | 337,034 | 323,578"]}),
    dict(q="Infosys guided a 20%–22% operating margin for FY26. What FY26 margin did it report?",
         a="Adjusted operating margin of 21% (reported 20.3% in the fact sheet) — within guidance.", type="cross_doc",
         ev={C25: ["Our margin guidance for financial year 2026 is 20% to 22%"],
             P25: ["operating margin at 20%-22%"],
             C26: ["Adjusted operating margin was stable at 21%"],
             P26: ["adjusted 1 operating margin at 21.0%", "21% adjusted operating margin"]}),

    # ---------------- Not answerable from this corpus ----------------
    dict(q="What was Infosys's revenue in FY2020?", a="Not found in the selected documents.", type="unanswerable", ev={}),
    dict(q="What is TCS's operating margin guidance for FY27?", a="Not found in the selected documents.", type="unanswerable", ev={}),
    dict(q="What was Infosys's closing share price on April 17, 2025?", a="Not found in the selected documents.", type="unanswerable", ev={}),
    dict(q="How many employees does Wipro have?", a="Not found in the selected documents.", type="unanswerable", ev={}),
]


def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def build(documents_dir: Path) -> list[dict]:
    from finsight.ingestion.parsers import extract_structured_document

    manifest = json.loads((HERE / "documents.json").read_text())["documents"]
    files = {d["key"]: documents_dir / d["file"] for d in manifest}
    pages_by_key: dict[str, list[dict]] = {}

    out: list[dict] = []
    errors: list[str] = []
    for n, item in enumerate(ITEMS, 1):
        rid = f"r{n:03d}"
        docs: dict[str, dict] = {}
        for key, quotes in item["ev"].items():
            if key not in pages_by_key:
                pages_by_key[key] = extract_structured_document(files[key])["pages"]
            pages = pages_by_key[key]
            found_pages: set[int] = set()
            for quote in quotes:
                hits = [p["page"] for p in pages if _norm(quote) in _norm(p["text"])]
                if not hits:
                    errors.append(f"{rid}: quote not found in {key}: {quote[:70]!r}")
                found_pages.update(hits)
            docs[key] = {"pages": sorted(found_pages), "evidence": quotes}
        out.append({
            "id": rid,
            "question": item["q"],
            "answer": item["a"],
            "type": item["type"],
            "answerable": item["type"] != "unanswerable",
            "docs": docs,
        })
    if errors:
        raise SystemExit("gold set does not match sources:\n  " + "\n  ".join(errors))
    return out


def main() -> None:
    import os
    os.environ.setdefault("SECRET_KEY", "gold-authoring")
    from finsight import config

    items = build(Path(config.DOCUMENTS_DIR))
    with OUT.open("w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    by_type: dict[str, int] = {}
    for it in items:
        by_type[it["type"]] = by_type.get(it["type"], 0) + 1
    print(f"wrote {len(items)} items to {OUT.relative_to(HERE.parent.parent)}: {by_type}")


if __name__ == "__main__":
    main()
