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
            lines.extend(
                [
                    f"### {rec.ticker} - {rec.decision}",
                    f"- Reasons: {', '.join(rec.reasons) if rec.reasons else 'N/A'}",
                    f"- Risks: {', '.join(rec.risks) if rec.risks else 'N/A'}",
                    f"- Assumptions: {', '.join(rec.assumptions) if rec.assumptions else 'N/A'}",
                    "",
                ]
            )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
