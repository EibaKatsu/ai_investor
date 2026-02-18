from __future__ import annotations

from datetime import date
from pathlib import Path

from ai_investor.models import PipelineResult
from ai_investor.reporting.tables import to_markdown_table


def write_report(result: PipelineResult, output_dir: str | Path, as_of: date) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{as_of.strftime('%Y%m%d')}_report.md"

    lines = [
        f"# AI Investor Report ({as_of.isoformat()})",
        "",
        "Quantitative score is split into two tracks: `Q(Price)` and `Q(Fund)`.",
        "Qualitative score is normalized to 0-100 (`Qual(100)`) after axis weighting.",
        "",
        "## Candidate Table",
        "",
        to_markdown_table(result.candidates),
        "",
        "## Top Recommendations",
        "",
    ]

    if not result.top_recommendations:
        lines.append("No recommendations generated.")
    else:
        for rec in result.top_recommendations:
            links_text = "; ".join(rec.source_links) if rec.source_links else "N/A"
            company_text = rec.company_name or "N/A"
            overview_text = rec.business_overview or "主力事業は直近開示の要確認"
            lines.extend(
                [
                    f"### {rec.ticker} {company_text}（{overview_text}） - {rec.decision}",
                    f"- Reasons: {', '.join(rec.reasons) if rec.reasons else 'N/A'}",
                    f"- Risks: {', '.join(rec.risks) if rec.risks else 'N/A'}",
                    f"- Assumptions: {', '.join(rec.assumptions) if rec.assumptions else 'N/A'}",
                    f"- 業種の景気動向・傾向: {', '.join(rec.industry_trends) if rec.industry_trends else 'N/A'}",
                    f"- 同業種内での強み: {', '.join(rec.peer_strengths) if rec.peer_strengths else 'N/A'}",
                    f"- 同業種内での弱み: {', '.join(rec.peer_weaknesses) if rec.peer_weaknesses else 'N/A'}",
                    f"- 具体的な出遅れ原因: {', '.join(rec.lag_causes) if rec.lag_causes else 'N/A'}",
                    f"- 投資判断への批判的意見: {', '.join(rec.critical_views) if rec.critical_views else 'N/A'}",
                    f"- Break Scenarios: {', '.join(rec.break_scenarios) if rec.break_scenarios else 'N/A'}",
                    f"- Reevaluation Triggers: {', '.join(rec.reevaluation_triggers) if rec.reevaluation_triggers else 'N/A'}",
                    f"- Source Links: {links_text}",
                    "",
                ]
            )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
