import json
import re
from pathlib import Path

from state_of_soroban.database import open_pool


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def clean(snippet: str | None) -> str:
    return re.sub(r"<[^>]+>", "", snippet or "").replace("\n", " ").strip()


def render(need: dict) -> str:
    rfp = need["rfp"]
    demand = rfp.get("demand", {})
    lines = [
        f"# {need['title']}",
        "",
        f"**Category:** {need['category']} · **Origin:** {need['origin']} · **Priority:** {rfp.get('priority')} · **Score:** {float(need['score']):.1f}",
        "",
        "## Problem",
        "",
        rfp.get("problem", need["summary"]),
        "",
        "## Gap against existing tools",
        "",
        rfp.get("gap", ""),
        "",
    ]
    for tool in rfp.get("existing_tools", []):
        lines.append(
            f"- [{tool['name']}]({tool.get('url') or ''}) ({tool['relation']})"
        )
    if rfp.get("gap_analysis"):
        lines += ["", "## What is missing, tool by tool", ""]
    for tool in rfp.get("gap_analysis", []):
        lines += [
            f"### {tool['name']}: {tool['verdict']}",
            "",
            tool["summary"],
            "",
        ]
        for item in tool["items"]:
            lines.append(f"- **{item['status']}**: {item['item']}")
            for ask in item["evidence"][:2]:
                lines.append(
                    f"  - related open issue: [{ask['title']}]({ask['url']}) ({ask['reactions']} reactions, {ask['comments']} comments)"
                )
        lines.append("")
    lines += ["", "## Who is affected", ""]
    lines += [
        f"- {s['stack']}: {s['repos']} repos" for s in rfp.get("who_is_affected", [])
    ]
    lines += ["", "## Proposed deliverables", ""]
    lines += [f"- {d}" for d in rfp.get("deliverables", [])] or [
        "- to be defined from the evidence"
    ]
    lines += ["", "## Success looks like", ""]
    lines += [f"- {d}" for d in rfp.get("success_metrics", [])] or ["- to be defined"]
    lines += ["", "## Demand numbers", ""]
    lines += [f"- {key.replace('_', ' ')}: {value}" for key, value in demand.items()]
    lines += ["", "## Evidence, most relevant first", ""]
    for item in rfp.get("evidence_highlights", []):
        lines.append(
            f"- [{item['repo']}]({item['url']}) ({item['kind']}, relevance {item['relevance']}): **{item['title']}**"
        )
        text = clean(item.get("snippet"))
        if text:
            lines.append(f"  > {text[:300]}")
    return "\n".join(lines) + "\n"


async def run_export(out: str, min_score: float) -> None:
    pool = await open_pool()
    try:
        rows = await pool.fetch(
            "SELECT id, title, category, origin, score, summary, rfp FROM tooling_needs "
            "WHERE score >= $1 ORDER BY score DESC",
            min_score,
        )
    finally:
        await pool.close()
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    index = [
        "# Tooling needs for the Stellar ecosystem",
        "",
        "| score | need | category | priority |",
        "|---|---|---|---|",
    ]
    records = []
    for row in rows:
        need = dict(row)
        need["rfp"] = (
            need["rfp"] if isinstance(need["rfp"], dict) else json.loads(need["rfp"])
        )
        name = f"{float(need['score']):05.1f}-{slug(need['title'])}.md"
        (target / name).write_text(render(need))
        index.append(
            f"| {float(need['score']):.1f} | [{need['title']}]({name}) | {need['category']} | {need['rfp'].get('priority')} |"
        )
        records.append({k: (float(v) if k == "score" else v) for k, v in need.items()})
    (target / "index.md").write_text("\n".join(index) + "\n")
    (target / "needs.json").write_text(json.dumps(records, indent=2, default=str))
    print(f"wrote {len(rows)} rfp drafts to {target}")
