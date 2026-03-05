#!/usr/bin/env python3
"""
compare_mappers.py — Side-by-Side Accuracy Comparison
=======================================================
Loads results from smart_mapper_results.json and legacy_mapper_results.json,
scores both against the ground truth in test_cases.json, and generates:
  1. A console summary with accuracy metrics
  2. report.html — a visual color-coded comparison table

Usage:
  python compare_mappers.py

Run legacy mapper first:  python legacy_mapper.py
Run AI mapper first:      python smart_mapper.py
Then compare:             python compare_mappers.py
"""

import json
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
TEST_CASES_PATH     = SCRIPT_DIR / "test_cases.json"
AI_RESULTS_PATH     = SCRIPT_DIR / "smart_mapper_results.json"
LEGACY_RESULTS_PATH = SCRIPT_DIR / "legacy_mapper_results.json"
REPORT_PATH         = SCRIPT_DIR / "report.html"

# ─── Load & Index ─────────────────────────────────────────────────────────────

def load_results(path: Path) -> dict:
    """Load a results file and return a dict keyed by room name."""
    if not path.exists():
        print(f"[WARN] Result file not found: {path}")
        return {}
    with open(path) as f:
        data = json.load(f)
    results = data.get("results", data) if isinstance(data, dict) else data
    return {r["name"]: r for r in results}

def load_test_cases() -> list:
    with open(TEST_CASES_PATH) as f:
        data = json.load(f)
    return data.get("test_cases", data)

# ─── Console Summary ──────────────────────────────────────────────────────────

def compute_accuracy(results_by_name: dict, test_cases: list) -> dict:
    total = len(test_cases)
    correct = 0
    hard_correct = 0
    hard_total = 0
    category_stats = {}  # expected_ibc -> {correct, total}

    for tc in test_cases:
        name = tc["name"]
        expected = tc["expected_ibc"]
        difficulty = tc.get("difficulty", "medium")
        result = results_by_name.get(name)

        if difficulty == "hard":
            hard_total += 1

        if not result:
            category_stats.setdefault(expected, {"correct": 0, "total": 0})["total"] += 1
            continue

        predicted = result.get("ibc_category", "")
        is_correct = (predicted == expected)

        if is_correct:
            correct += 1
            if difficulty == "hard":
                hard_correct += 1

        cat = category_stats.setdefault(expected, {"correct": 0, "total": 0})
        cat["total"] += 1
        if is_correct:
            cat["correct"] += 1

    return {
        "total": total,
        "correct": correct,
        "accuracy_pct": round(correct / total * 100, 1) if total else 0,
        "hard_correct": hard_correct,
        "hard_total": hard_total,
        "hard_accuracy_pct": round(hard_correct / hard_total * 100, 1) if hard_total else 0,
        "by_category": category_stats,
    }

def print_summary(ai_stats: dict, legacy_stats: dict):
    print(f"\n{'='*70}")
    print("  IBC MAPPER COMPARISON REPORT")
    print(f"{'='*70}")
    print(f"{'Metric':<35} {'AI Mapper':>15} {'Legacy Mapper':>15}")
    print(f"{'-'*70}")
    print(f"{'Overall Accuracy':<35} {ai_stats['accuracy_pct']:>14.1f}% {legacy_stats['accuracy_pct']:>14.1f}%")
    #print(f"{'Correct / Total':<35} {f\"{ai_stats['correct']}/{ai_stats['total']}\":>15} {f\"{legacy_stats['correct']}/{legacy_stats['total']}\":>15}")
    print(f"{'Hard Cases Accuracy':<35} {ai_stats['hard_accuracy_pct']:>14.1f}% {legacy_stats['hard_accuracy_pct']:>14.1f}%")
    delta = ai_stats["accuracy_pct"] - legacy_stats["accuracy_pct"]
    sign = "+" if delta >= 0 else ""
    print(f"\n  AI Mapper improvement: {sign}{delta:.1f} percentage points")

    print(f"\n{'─'*70}")
    print("  Per-Category Breakdown")
    print(f"{'─'*70}")
    print(f"{'Category':<38} {'AI':>8} {'Legacy':>10}")
    print(f"{'-'*70}")
    all_cats = set(ai_stats["by_category"]) | set(legacy_stats["by_category"])
    for cat in sorted(all_cats):
        ai_c = ai_stats["by_category"].get(cat, {"correct": 0, "total": 0})
        leg_c = legacy_stats["by_category"].get(cat, {"correct": 0, "total": 0})
        ai_pct = f"{ai_c['correct']}/{ai_c['total']}"
        leg_pct = f"{leg_c['correct']}/{leg_c['total']}"
        print(f"  {cat:<36} {ai_pct:>8} {leg_pct:>10}")

    print(f"{'='*70}\n")

# ─── HTML Report ──────────────────────────────────────────────────────────────

def build_html_report(test_cases: list, ai_results: dict, legacy_results: dict,
                       ai_stats: dict, legacy_stats: dict) -> str:
    timestamp = datetime.now().strftime("%B %d, %Y at %H:%M")
    delta = ai_stats["accuracy_pct"] - legacy_stats["accuracy_pct"]
    delta_str = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"

    rows = []
    for tc in test_cases:
        name = tc["name"]
        expected = tc["expected_ibc"]
        difficulty = tc.get("difficulty", "medium")
        area = tc.get("area_sqft", 0)
        capacity = tc.get("capacity", 0)
        density = f"{area/capacity:.0f}" if capacity > 0 else "N/A"

        ai_r = ai_results.get(name, {})
        leg_r = legacy_results.get(name, {})

        ai_cat = ai_r.get("ibc_category", "—")
        ai_conf = ai_r.get("confidence", "—")
        ai_reason = ai_r.get("reasoning", "N/A")
        ai_correct = ai_cat == expected

        leg_cat = leg_r.get("ibc_category", "—")
        leg_reason = leg_r.get("reasoning", "N/A")
        leg_correct = leg_cat == expected

        diff_badge = {"hard": "🔴 Hard", "medium": "🟡 Medium", "easy": "🟢 Easy"}.get(difficulty, "")
        ai_badge = "✅" if ai_correct else "❌"
        leg_badge = "✅" if leg_correct else "❌"

        ai_row_class = "correct" if ai_correct else "wrong"
        leg_row_class = "correct" if leg_correct else "wrong"

        conf_color = {"high": "#22c55e", "medium": "#f59e0b", "low": "#ef4444"}.get(ai_conf, "#94a3b8")

        rows.append(f"""
        <tr>
          <td class="room-cell">
            <span class="room-name">{name}</span>
            <span class="difficulty-badge">{diff_badge}</span>
            <div class="room-meta">{tc.get('enclosure','?')} · {capacity}p · {area} sqft · {density} sqft/p</div>
          </td>
          <td class="expected-cell">{expected}</td>
          <td class="mapper-cell {ai_row_class}">
            <span class="result-icon">{ai_badge}</span>
            <span class="cat-name">{ai_cat}</span>
            <span class="conf-badge" style="background:{conf_color}20;color:{conf_color};border:1px solid {conf_color}40">{ai_conf}</span>
            <div class="reasoning-text">{ai_reason}</div>
          </td>
          <td class="mapper-cell {leg_row_class}">
            <span class="result-icon">{leg_badge}</span>
            <span class="cat-name">{leg_cat}</span>
            <div class="reasoning-text">{leg_reason}</div>
          </td>
        </tr>""")

    rows_html = "\n".join(rows)

    # Category breakdown rows
    cat_rows = []
    all_cats = sorted(set(ai_stats["by_category"]) | set(legacy_stats["by_category"]))
    for cat in all_cats:
        ai_c = ai_stats["by_category"].get(cat, {"correct": 0, "total": 0})
        leg_c = legacy_stats["by_category"].get(cat, {"correct": 0, "total": 0})
        ai_pct = ai_c["correct"] / ai_c["total"] * 100 if ai_c["total"] else 0
        leg_pct = leg_c["correct"] / leg_c["total"] * 100 if leg_c["total"] else 0
        ai_bar = f'<div class="bar ai-bar" style="width:{ai_pct:.0f}%"></div>'
        leg_bar = f'<div class="bar leg-bar" style="width:{leg_pct:.0f}%"></div>'
        cat_rows.append(f"""
        <tr>
          <td class="cat-label">{cat}</td>
          <td><div class="bar-container">{ai_bar}<span class="bar-label">{ai_c["correct"]}/{ai_c["total"]}</span></div></td>
          <td><div class="bar-container">{leg_bar}<span class="bar-label">{leg_c["correct"]}/{leg_c["total"]}</span></div></td>
        </tr>""")
    cat_rows_html = "\n".join(cat_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Salt-Mine · IBC Mapper Comparison Report</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg: #0a0e1a;
      --bg2: #0f1629;
      --bg3: #141d35;
      --surface: #1a2340;
      --surface2: #202b4a;
      --border: #2a3558;
      --text: #e2e8f0;
      --text-muted: #64748b;
      --text-dim: #94a3b8;
      --ai-color: #6366f1;
      --ai-glow: #6366f140;
      --leg-color: #f59e0b;
      --leg-glow: #f59e0b30;
      --correct: #22c55e;
      --wrong: #ef4444;
      --accent: #38bdf8;
    }}

    body {{
      font-family: 'Inter', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.6;
    }}

    /* ── Header ── */
    .header {{
      background: linear-gradient(135deg, #0f1629 0%, #1a1040 50%, #0f1629 100%);
      border-bottom: 1px solid var(--border);
      padding: 48px 40px 40px;
      position: relative;
      overflow: hidden;
    }}
    .header::before {{
      content: '';
      position: absolute;
      top: -100px; left: -100px;
      width: 400px; height: 400px;
      background: radial-gradient(circle, #6366f120 0%, transparent 70%);
      pointer-events: none;
    }}
    .header-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--ai-glow);
      border: 1px solid var(--ai-color)50;
      color: var(--ai-color);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      padding: 4px 12px;
      border-radius: 100px;
      margin-bottom: 16px;
    }}
    .header h1 {{
      font-size: 32px;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin-bottom: 8px;
    }}
    .header h1 span {{ color: var(--ai-color); }}
    .header-meta {{ color: var(--text-muted); font-size: 13px; }}

    /* ── Score Cards ── */
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      padding: 32px 40px;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      position: relative;
      overflow: hidden;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    .card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 32px #00000040; }}
    .card.ai-card {{ border-color: var(--ai-color)60; box-shadow: 0 0 0 1px var(--ai-color)20 inset; }}
    .card.delta-card {{ border-color: var(--correct)60; background: #0f291e; }}
    .card-label {{ font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; }}
    .card-value {{ font-size: 36px; font-weight: 700; letter-spacing: -0.02em; }}
    .card.ai-card .card-value {{ color: var(--ai-color); }}
    .card.leg-card .card-value {{ color: var(--leg-color); }}
    .card.delta-card .card-value {{ color: var(--correct); }}
    .card-sub {{ font-size: 12px; color: var(--text-muted); margin-top: 4px; }}

    /* ── Section ── */
    .section {{ padding: 0 40px 40px; }}
    .section-title {{
      font-size: 13px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 20px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
    }}

    /* ── Category Breakdown ── */
    .breakdown-table {{ width: 100%; border-collapse: collapse; }}
    .breakdown-table th {{
      text-align: left;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--text-muted);
      padding: 8px 12px;
    }}
    .cat-label {{ font-size: 13px; font-weight: 500; padding: 10px 12px; color: var(--text-dim); }}
    .bar-container {{ display: flex; align-items: center; gap: 8px; padding: 6px 12px; }}
    .bar {{ height: 8px; border-radius: 4px; min-width: 2px; transition: width 0.6s ease; }}
    .ai-bar {{ background: linear-gradient(90deg, var(--ai-color), #818cf8); }}
    .leg-bar {{ background: linear-gradient(90deg, var(--leg-color), #fbbf24); }}
    .bar-label {{ font-size: 12px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; white-space: nowrap; }}

    /* ── Main Table ── */
    .table-wrap {{
      overflow-x: auto;
      border-radius: 16px;
      border: 1px solid var(--border);
    }}
    .main-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .main-table thead {{
      background: var(--surface);
      border-bottom: 2px solid var(--border);
    }}
    .main-table th {{
      padding: 14px 16px;
      text-align: left;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--text-muted);
    }}
    .main-table th.ai-header {{ color: var(--ai-color); }}
    .main-table th.leg-header {{ color: var(--leg-color); }}
    .main-table tbody tr {{
      border-bottom: 1px solid var(--border);
      transition: background 0.15s;
    }}
    .main-table tbody tr:hover {{ background: var(--surface2); }}
    .main-table tbody tr:last-child {{ border-bottom: none; }}

    .room-cell {{ padding: 16px; min-width: 200px; }}
    .room-name {{ display: block; font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 4px; }}
    .difficulty-badge {{ font-size: 10px; margin-left: 6px; }}
    .room-meta {{ font-size: 11px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; margin-top: 4px; }}

    .expected-cell {{
      padding: 16px;
      font-size: 12px;
      font-weight: 500;
      color: var(--accent);
      font-family: 'JetBrains Mono', monospace;
      min-width: 180px;
    }}

    .mapper-cell {{
      padding: 14px 16px;
      vertical-align: top;
      min-width: 260px;
      border-left: 3px solid transparent;
    }}
    .mapper-cell.correct {{ border-left-color: var(--correct); background: #0b2015; }}
    .mapper-cell.wrong {{ border-left-color: var(--wrong); background: #1e0b0b; }}

    .result-icon {{ font-size: 14px; margin-right: 6px; }}
    .cat-name {{ font-weight: 600; font-size: 13px; }}
    .mapper-cell.correct .cat-name {{ color: var(--correct); }}
    .mapper-cell.wrong .cat-name {{ color: var(--wrong); }}

    .conf-badge {{
      display: inline-block;
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 1px 6px;
      border-radius: 4px;
      margin-left: 6px;
      vertical-align: middle;
    }}

    .reasoning-text {{
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 8px;
      line-height: 1.5;
      font-style: italic;
    }}

    /* ── Footer ── */
    .footer {{
      text-align: center;
      padding: 32px;
      color: var(--text-muted);
      font-size: 12px;
      border-top: 1px solid var(--border);
    }}
  </style>
</head>
<body>

  <div class="header">
    <div class="header-badge">⚡ Salt-Mine · POC Report</div>
    <h1>IBC Space Function <span>Mapper Comparison</span></h1>
    <p class="header-meta">AI Mapper (Gemini 2.0 Flash) vs. Legacy Heuristic Mapper · Generated {timestamp}</p>
  </div>

  <div class="cards">
    <div class="card ai-card">
      <div class="card-label">🤖 AI Mapper Accuracy</div>
      <div class="card-value">{ai_stats['accuracy_pct']}%</div>
      <div class="card-sub">{ai_stats['correct']} of {ai_stats['total']} correct</div>
    </div>
    <div class="card leg-card">
      <div class="card-label">📜 Legacy Mapper Accuracy</div>
      <div class="card-value">{legacy_stats['accuracy_pct']}%</div>
      <div class="card-sub">{legacy_stats['correct']} of {legacy_stats['total']} correct</div>
    </div>
    <div class="card delta-card">
      <div class="card-label">📈 Improvement</div>
      <div class="card-value">{delta_str}%</div>
      <div class="card-sub">percentage points gained</div>
    </div>
    <div class="card ai-card">
      <div class="card-label">🔴 Hard Cases (AI)</div>
      <div class="card-value">{ai_stats['hard_accuracy_pct']}%</div>
      <div class="card-sub">{ai_stats['hard_correct']} of {ai_stats['hard_total']} creative names</div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">Per-Category Accuracy</div>
    <table class="breakdown-table">
      <thead>
        <tr>
          <th style="width:38%">IBC Category</th>
          <th style="color:var(--ai-color)">🤖 AI Mapper</th>
          <th style="color:var(--leg-color)">📜 Legacy Mapper</th>
        </tr>
      </thead>
      <tbody>
        {cat_rows_html}
      </tbody>
    </table>
  </div>

  <div class="section">
    <div class="section-title">Room-by-Room Breakdown</div>
    <div class="table-wrap">
      <table class="main-table">
        <thead>
          <tr>
            <th>Room</th>
            <th>Expected (Ground Truth)</th>
            <th class="ai-header">🤖 AI Mapper</th>
            <th class="leg-header">📜 Legacy Mapper</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    Salt-Mine IBC Mapper POC · Antigravity Agent · {timestamp}
  </div>

</body>
</html>"""

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    test_cases = load_test_cases()
    ai_results = load_results(AI_RESULTS_PATH)
    legacy_results = load_results(LEGACY_RESULTS_PATH)

    ai_stats = compute_accuracy(ai_results, test_cases)
    legacy_stats = compute_accuracy(legacy_results, test_cases)

    print_summary(ai_stats, legacy_stats)

    html = build_html_report(test_cases, ai_results, legacy_results, ai_stats, legacy_stats)
    with open(REPORT_PATH, "w") as f:
        f.write(html)

    print(f"✅ HTML report saved → {REPORT_PATH}")
    print(f"   Open with: open {REPORT_PATH}\n")

if __name__ == "__main__":
    main()
