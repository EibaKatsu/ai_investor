from __future__ import annotations

from ai_investor.models import Candidate


def to_markdown_table(candidates: list[Candidate]) -> str:
    header = (
        "|Ticker|Company|Sector|Quant|Qual|Composite|Excluded|Reasons|\n"
        "|---|---|---|---:|---:|---:|---|---|"
    )
    rows = []
    for candidate in candidates:
        rows.append(
            "|{ticker}|{name}|{sector}|{quant:.2f}|{qual:.2f}|{comp:.2f}|{excluded}|{reasons}|".format(
                ticker=candidate.ticker,
                name=candidate.company_name,
                sector=candidate.sector,
                quant=candidate.quantitative_score,
                qual=candidate.qualitative_score_total,
                comp=candidate.composite_score,
                excluded="yes" if candidate.excluded else "no",
                reasons=", ".join(candidate.exclusion_reasons),
            )
        )
    return header + ("\n" + "\n".join(rows) if rows else "")
