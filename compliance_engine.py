#!/usr/bin/env python3
"""
compliance_engine.py — Salt-Mine IBC Compliance Engine
=======================================================
Interactive CLI that takes project inputs, runs AI-powered room mapping,
then executes 3 IBC compliance checks with a required-vs-actual comparison.

Compliance Checks:
  1. Occupancy Load   (IBC Table 1004.5)
  2. Plumbing         (IBC Table 2902.1)
  3. Means of Egress  (IBC Chapter 10, Sections 1005.1 + 1006)

Usage:
  python compliance_engine.py           # interactive mode
  python compliance_engine.py --demo    # run with built-in demo data (no API key needed for demo)
  python compliance_engine.py --ai      # enable AI room mapping (requires GEMINI_API_KEY)

Output:
  compliance_results.json
  compliance_report.html
"""

import os
import json
import math
import argparse
from pathlib import Path
from datetime import datetime

SCRIPT_DIR   = Path(__file__).parent
IBC_PATH     = SCRIPT_DIR / "ibc_rules.json"
RESULTS_PATH = SCRIPT_DIR / "compliance_results.json"
REPORT_PATH  = SCRIPT_DIR / "compliance_report.html"

# ─── IBC Rules Loader ─────────────────────────────────────────────────────────

def load_ibc() -> dict:
    with open(IBC_PATH) as f:
        return json.load(f)

# ─── Input Collection ─────────────────────────────────────────────────────────

def prompt(label: str, default=None, cast=str):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        val = input(f"  {label}{suffix}: ").strip()
        if not val and default is not None:
            return default
        try:
            return cast(val) if val else default
        except (ValueError, TypeError):
            print(f"  ⚠  Please enter a valid {cast.__name__}.")

def collect_inputs() -> dict:
    print("\n" + "═"*60)
    print("  SALT-MINE · IBC Compliance Engine")
    print("  International Building Code — Compliance Checker")
    print("═"*60)

    print("\n── Project Info ──────────────────────────────────")
    project_name = prompt("Project name", "Tower A POC")
    num_floors   = prompt("Number of floors occupied", 2, int)
    sqft_per_floor = prompt("Usable area per floor (sq ft)", 10000, float)
    is_sprinklered = prompt("Is the building sprinklered? (yes/no)", "yes").lower().startswith("y")

    print("\n── Headcount ─────────────────────────────────────")
    total_headcount = prompt("Total headcount (all floors)", 90, int)
    male_pct     = prompt("Approximate % male occupants", 50, int)
    female_pct   = 100 - male_pct
    print(f"  → Male: {male_pct}%  |  Female: {female_pct}%")

    regularity = prompt("Occupancy regularity (permanent/transient/mixed)", "permanent")

    print("\n── Spaces / Rooms ────────────────────────────────")
    num_meeting  = prompt("Number of meeting rooms (total, all floors)", 3, int)
    meeting_cap  = prompt("Average meeting room capacity (people)", 10, int)

    print("\n── Actual Design Values ──────────────────────────")
    print("  (Enter '?' to mark as 'Not provided / TBD')")
    actual_exits_per_floor  = prompt("Actual exits per floor", 2, int)
    actual_wc_male          = prompt("Actual WC fixtures (male, per floor)", 2, int)
    actual_wc_female        = prompt("Actual WC fixtures (female, per floor)", 2, int)
    actual_lavatories       = prompt("Actual lavatories (sinks, per floor)", 3, int)
    actual_drinking_fountains = prompt("Actual drinking fountains (whole building)", 1, int)
    actual_service_sinks    = prompt("Actual service sinks (whole building)", 1, int)

    return {
        "project_name": project_name,
        "num_floors": num_floors,
        "sqft_per_floor": sqft_per_floor,
        "total_sqft": num_floors * sqft_per_floor,
        "is_sprinklered": is_sprinklered,
        "total_headcount": total_headcount,
        "headcount_per_floor": math.ceil(total_headcount / num_floors),
        "male_pct": male_pct,
        "female_pct": female_pct,
        "regularity": regularity,
        "num_meeting_rooms": num_meeting,
        "meeting_room_capacity": meeting_cap,
        "actual": {
            "exits_per_floor": actual_exits_per_floor,
            "wc_male_per_floor": actual_wc_male,
            "wc_female_per_floor": actual_wc_female,
            "lavatories_per_floor": actual_lavatories,
            "drinking_fountains_total": actual_drinking_fountains,
            "service_sinks_total": actual_service_sinks,
        }
    }

def demo_inputs() -> dict:
    """Pre-filled demo inputs so the engine can run without interaction."""
    print("\n[DEMO MODE] Using Tower A POC demo data...\n")
    return {
        "project_name": "Tower A POC",
        "num_floors": 2,
        "sqft_per_floor": 10000.0,
        "total_sqft": 20000.0,
        "is_sprinklered": True,
        "total_headcount": 90,
        "headcount_per_floor": 45,
        "male_pct": 50,
        "female_pct": 50,
        "regularity": "permanent",
        "num_meeting_rooms": 3,
        "meeting_room_capacity": 10,
        "actual": {
            "exits_per_floor": 2,
            "wc_male_per_floor": 2,
            "wc_female_per_floor": 2,
            "lavatories_per_floor": 3,
            "drinking_fountains_total": 1,
            "service_sinks_total": 1,
        }
    }

# ─── IBC Occupancy Load Check ─────────────────────────────────────────────────

def check_occupancy_load(project: dict, ibc: dict) -> dict:
    """IBC Table 1004.5 — Occupancy Load Calculation"""
    load_factor = 150  # Business Areas (default — AI mapper would refine per room)
    sqft = project["sqft_per_floor"]
    headcount_per_floor = project["headcount_per_floor"]
    meeting_load_per_floor = math.ceil(project["num_meeting_rooms"] / project["num_floors"]) * project["meeting_room_capacity"]

    # Net usable office area (subtract estimated meeting room sqft)
    meeting_sqft_per_floor = math.ceil(project["num_meeting_rooms"] / project["num_floors"]) * 300
    office_sqft = max(sqft - meeting_sqft_per_floor, sqft * 0.6)

    allowed_office   = math.floor(office_sqft / load_factor)
    allowed_meeting  = math.floor(meeting_sqft_per_floor / 15)  # Assembly-Unconcentrated
    allowed_total    = allowed_office + allowed_meeting
    actual_total     = headcount_per_floor + meeting_load_per_floor

    checks = [
        {
            "check": "Max Occupancy Load — Office Areas",
            "ibc_ref": "IBC Table 1004.5",
            "formula": f"{office_sqft:,.0f} sqft ÷ {load_factor} sqft/person",
            "required": f"≤ {allowed_office} persons",
            "required_val": allowed_office,
            "actual": f"{headcount_per_floor} persons (seated staff per floor)",
            "actual_val": headcount_per_floor,
            "pass": headcount_per_floor <= allowed_office,
            "note": "Business Areas load factor 150 gross sqft/person (IBC Table 1004.5)"
        },
        {
            "check": "Max Occupancy Load — Meeting Rooms",
            "ibc_ref": "IBC Table 1004.5",
            "formula": f"{meeting_sqft_per_floor:,.0f} sqft ÷ 15 sqft/person (Assembly–Uncon.)",
            "required": f"≤ {allowed_meeting} persons",
            "required_val": allowed_meeting,
            "actual": f"{meeting_load_per_floor} persons (meeting rooms per floor)",
            "actual_val": meeting_load_per_floor,
            "pass": meeting_load_per_floor <= allowed_meeting,
            "note": "Assembly–Unconcentrated (tables & chairs) load factor 15 net sqft/person"
        },
        {
            "check": "Combined Floor Occupancy",
            "ibc_ref": "IBC 1004.5 + 1004.8",
            "formula": f"Office allowed + Meeting allowed = {allowed_office} + {allowed_meeting}",
            "required": f"≤ {allowed_total} persons total per floor",
            "required_val": allowed_total,
            "actual": f"{actual_total} persons (staff + meeting peak)",
            "actual_val": actual_total,
            "pass": actual_total <= allowed_total,
            "note": "Combined peak occupancy per floor; meeting rooms may not all be full simultaneously"
        },
    ]

    return {
        "module": "Occupancy Load",
        "ibc_chapter": "IBC Chapter 10 — Table 1004.5",
        "overall_pass": all(c["pass"] for c in checks),
        "checks": checks,
        "summary": {
            "sqft_per_floor": sqft,
            "load_factor_office": load_factor,
            "load_factor_meeting": 15,
            "allowed_per_floor": allowed_total,
            "actual_per_floor": actual_total,
        }
    }

# ─── IBC Plumbing Check ───────────────────────────────────────────────────────

def check_plumbing(project: dict, ibc: dict) -> dict:
    """IBC Table 2902.1 — Minimum Plumbing Fixtures"""
    pt = ibc["plumbing_table"]["fixtures"]
    occ = project["headcount_per_floor"]
    male_occ   = math.ceil(occ * project["male_pct"] / 100)
    female_occ = occ - male_occ
    act = project["actual"]

    req_wc_male   = max(math.ceil(male_occ   / pt["water_closets"]["male"]["ratio"]),   pt["water_closets"]["minimum"])
    req_wc_female = max(math.ceil(female_occ / pt["water_closets"]["female"]["ratio"]), pt["water_closets"]["minimum"])
    req_lav       = max(math.ceil(occ / pt["lavatories"]["ratio"]),                      pt["lavatories"]["minimum"])
    req_df        = max(math.ceil(project["total_headcount"] / pt["drinking_fountains"]["ratio"]), pt["drinking_fountains"]["minimum"])
    req_ss        = pt["service_sinks"]["minimum"] * project["num_floors"]

    checks = [
        {
            "check": "Water Closets — Male (per floor)",
            "ibc_ref": "IBC Table 2902.1",
            "formula": f"⌈{male_occ} male occupants ÷ 50⌉",
            "required": f"≥ {req_wc_male} WC(s)",
            "required_val": req_wc_male,
            "actual": f"{act['wc_male_per_floor']} WC(s) provided",
            "actual_val": act["wc_male_per_floor"],
            "pass": act["wc_male_per_floor"] >= req_wc_male,
            "note": "IBC 2902.1: 1 WC per 50 male occupants for Business (B) occupancy"
        },
        {
            "check": "Water Closets — Female (per floor)",
            "ibc_ref": "IBC Table 2902.1",
            "formula": f"⌈{female_occ} female occupants ÷ 25⌉",
            "required": f"≥ {req_wc_female} WC(s)",
            "required_val": req_wc_female,
            "actual": f"{act['wc_female_per_floor']} WC(s) provided",
            "actual_val": act["wc_female_per_floor"],
            "pass": act["wc_female_per_floor"] >= req_wc_female,
            "note": "IBC 2902.1: 1 WC per 25 female occupants for Business (B) occupancy"
        },
        {
            "check": "Lavatories / Sinks (per floor)",
            "ibc_ref": "IBC Table 2902.1",
            "formula": f"⌈{occ} occupants ÷ 40⌉",
            "required": f"≥ {req_lav} lavatory(ies)",
            "required_val": req_lav,
            "actual": f"{act['lavatories_per_floor']} lavatory(ies) provided",
            "actual_val": act["lavatories_per_floor"],
            "pass": act["lavatories_per_floor"] >= req_lav,
            "note": "IBC 2902.1: 1 lavatory per 40 occupants"
        },
        {
            "check": "Drinking Fountains (whole building)",
            "ibc_ref": "IBC Table 2902.1",
            "formula": f"⌈{project['total_headcount']} total occupants ÷ 100⌉",
            "required": f"≥ {req_df} drinking fountain(s)",
            "required_val": req_df,
            "actual": f"{act['drinking_fountains_total']} provided",
            "actual_val": act["drinking_fountains_total"],
            "pass": act["drinking_fountains_total"] >= req_df,
            "note": "IBC 2902.1: 1 per 100 occupants; ADA requires 2 types (accessible + standard height)"
        },
        {
            "check": "Service Sinks (whole building)",
            "ibc_ref": "IBC Table 2902.1",
            "formula": f"1 per floor × {project['num_floors']} floors",
            "required": f"≥ {req_ss} service sink(s)",
            "required_val": req_ss,
            "actual": f"{act['service_sinks_total']} provided",
            "actual_val": act["service_sinks_total"],
            "pass": act["service_sinks_total"] >= req_ss,
            "note": "IBC 2902.1: Minimum 1 service sink per floor"
        },
    ]

    return {
        "module": "Plumbing",
        "ibc_chapter": "IBC Chapter 29 — Table 2902.1",
        "overall_pass": all(c["pass"] for c in checks),
        "checks": checks,
        "summary": {
            "occupants_per_floor": occ,
            "male_occupants": male_occ,
            "female_occupants": female_occ,
        }
    }

# ─── IBC Egress Check ─────────────────────────────────────────────────────────

def check_egress(project: dict, ibc: dict) -> dict:
    """IBC Chapter 10 — Means of Egress"""
    et = ibc["egress_table"]
    occ_per_floor = project["headcount_per_floor"]
    act = project["actual"]

    # Number of required exits
    req_exits = 1
    for threshold in et["exit_count_thresholds"]:
        if occ_per_floor <= threshold["max_occupants"]:
            req_exits = threshold["min_exits"]
            break

    # Door width
    door_factor = et["door_width"]["factor_inches_per_occupant"]
    door_min    = et["door_width"]["minimum_clear_inches"]
    req_door_width = max(round(occ_per_floor * door_factor, 1), door_min)

    # Corridor width
    req_corridor = et["corridor_width"]["over_49_occupants_inches"] if occ_per_floor > 49 \
                   else et["corridor_width"]["under_50_occupants_inches"]

    # Travel distance
    travel_limit = et["travel_distance"]["sprinklered_ft"] if project["is_sprinklered"] \
                   else et["travel_distance"]["unsprinklered_ft"]

    # Stair width
    stair_factor = et["stair_width"]["factor_inches_per_occupant"]
    stair_min    = et["stair_width"]["minimum_inches"]
    req_stair_width = max(round(occ_per_floor * stair_factor, 1), stair_min)

    sprinkler_label = "sprinklered" if project["is_sprinklered"] else "unsprinklered"

    checks = [
        {
            "check": "Number of Exits (per floor)",
            "ibc_ref": "IBC 1006.3",
            "formula": f"{occ_per_floor} occupants/floor → exit count threshold",
            "required": f"≥ {req_exits} exit(s)",
            "required_val": req_exits,
            "actual": f"{act['exits_per_floor']} exit(s) provided",
            "actual_val": act["exits_per_floor"],
            "pass": act["exits_per_floor"] >= req_exits,
            "note": f"IBC 1006.3: {occ_per_floor} occupants requires ≥{req_exits} exit(s)"
        },
        {
            "check": "Exit Door Clear Width",
            "ibc_ref": "IBC 1005.1",
            "formula": f"{occ_per_floor} occ × 0.2 in/occ = {occ_per_floor * 0.2:.1f}\" (min {door_min}\")",
            "required": f"≥ {req_door_width}\" clear width per door leaf",
            "required_val": req_door_width,
            "actual": "Not provided — verify from drawings",
            "actual_val": None,
            "pass": None,
            "note": "IBC 1005.1: 0.2 in per occupant, never less than 32\" clear"
        },
        {
            "check": "Corridor Minimum Width",
            "ibc_ref": "IBC 1005.1",
            "formula": f"{occ_per_floor} occupants/floor (>49 → 44\" minimum)",
            "required": f"≥ {req_corridor}\" wide",
            "required_val": req_corridor,
            "actual": "Not provided — verify from drawings",
            "actual_val": None,
            "pass": None,
            "note": "IBC 1005.1: 44\" min corridor width for >49 occupants; 36\" for ≤49"
        },
        {
            "check": "Maximum Travel Distance to Exit",
            "ibc_ref": "IBC 1017.2",
            "formula": f"Business (B), {sprinkler_label} → {travel_limit} ft limit",
            "required": f"≤ {travel_limit} ft from any point to exit",
            "required_val": travel_limit,
            "actual": "Not provided — verify from drawings",
            "actual_val": None,
            "pass": None,
            "note": f"IBC 1017.2: Business B occupancy, {sprinkler_label}: {travel_limit} ft max travel distance"
        },
        {
            "check": "Stair Minimum Width",
            "ibc_ref": "IBC 1005.1",
            "formula": f"{occ_per_floor} occ × 0.3 in/occ = {occ_per_floor * 0.3:.1f}\" (min {stair_min}\")",
            "required": f"≥ {req_stair_width}\" stair width",
            "required_val": req_stair_width,
            "actual": "Not provided — verify from drawings",
            "actual_val": None,
            "pass": None,
            "note": "IBC 1005.1: 0.3 in per occupant, never less than 44\""
        },
    ]

    # Only score checks where actual_val is known
    scoreable = [c for c in checks if c["pass"] is not None]

    return {
        "module": "Egress",
        "ibc_chapter": "IBC Chapter 10 — Sections 1005.1, 1006, 1017",
        "overall_pass": all(c["pass"] for c in scoreable) if scoreable else None,
        "checks": checks,
        "summary": {
            "occupants_per_floor": occ_per_floor,
            "required_exits": req_exits,
            "required_door_width_in": req_door_width,
            "required_corridor_width_in": req_corridor,
            "required_stair_width_in": req_stair_width,
            "max_travel_distance_ft": travel_limit,
            "sprinklered": project["is_sprinklered"],
        }
    }

# ─── AI Mapper Integration ────────────────────────────────────────────────────

def get_room_mappings(project: dict, use_ai: bool) -> list:
    """Return a list of room mapping results (AI or legacy)."""
    rooms = []
    floors = project["num_floors"]
    per_floor = max(1, project["num_meeting_rooms"] // floors)

    # Meeting rooms
    for i in range(1, project["num_meeting_rooms"] + 1):
        rooms.append({
            "name": f"Meeting Room {i}",
            "enclosure": "Closed",
            "capacity": project["meeting_room_capacity"],
            "area_sqft": 300
        })
    # Open office (one per floor)
    for i in range(1, floors + 1):
        rooms.append({
            "name": f"Open Office — Floor {i}",
            "enclosure": "Open",
            "capacity": math.ceil(project["headcount_per_floor"] * 0.8),
            "area_sqft": int(project["sqft_per_floor"] * 0.7)
        })

    if use_ai:
        try:
            from smart_mapper import load_ibc_rules, get_model, classify_block
            rules = load_ibc_rules()
            model = get_model(rules)
            results = []
            for r in rooms:
                c = classify_block(model, r)
                results.append({**r, **c, "mapper": "AI (Gemini 2.0 Flash)"})
            return results
        except Exception as e:
            print(f"  [WARN] AI mapper unavailable ({e}). Falling back to legacy.")

    # Legacy fallback
    from legacy_mapper import legacy_classify
    return [{**r, **legacy_classify(r), "mapper": "Legacy (Keyword)"} for r in rooms]

# ─── Print Console Summary ────────────────────────────────────────────────────

def print_results(modules: list):
    symbols = {True: "✅ PASS", False: "❌ FAIL", None: "⚠️  N/A"}
    for mod in modules:
        print(f"\n── {mod['module']} ({mod['ibc_chapter']}) ──")
        for c in mod["checks"]:
            sym = symbols.get(c.get("pass"))
            print(f"  {sym}  {c['check']}")
            print(f"         Required : {c['required']}")
            print(f"         Actual   : {c['actual']}")

# ─── HTML Report Generator ────────────────────────────────────────────────────

def _pass_badge(val) -> str:
    if val is True:
        return '<span class="badge pass">✅ PASS</span>'
    elif val is False:
        return '<span class="badge fail">❌ FAIL</span>'
    return '<span class="badge na">⚠️ N/A — Verify from Drawings</span>'

def _check_rows(checks: list) -> str:
    rows = []
    for c in checks:
        badge = _pass_badge(c.get("pass"))
        actual_display = c["actual"] if c["actual_val"] is not None else \
                         f'<em style="color:#64748b">{c["actual"]}</em>'
        rows.append(f"""
        <tr>
          <td class="check-name">{c['check']}<div class="ibc-ref">{c['ibc_ref']}</div></td>
          <td class="formula">{c['formula']}</td>
          <td class="required">{c['required']}</td>
          <td class="actual">{actual_display}</td>
          <td class="status">{badge}</td>
        </tr>
        <tr class="note-row"><td colspan="5"><span class="note">📖 {c['note']}</span></td></tr>""")
    return "\n".join(rows)

def _module_section(mod: dict, idx: int) -> str:
    icons = {"Occupancy Load": "👥", "Plumbing": "🚿", "Egress": "🚪"}
    icon = icons.get(mod["module"], "📋")
    overall = mod.get("overall_pass")
    header_class = "module-pass" if overall is True else ("module-fail" if overall is False else "module-na")
    status_text = "ALL PASS" if overall is True else ("ISSUES FOUND" if overall is False else "VERIFY REQUIRED")
    status_class = "pass" if overall is True else ("fail" if overall is False else "na")

    return f"""
    <div class="module-card" id="module-{idx}">
      <div class="module-header {header_class}">
        <div class="module-title">
          <span class="module-icon">{icon}</span>
          <div>
            <div class="module-name">{mod['module']}</div>
            <div class="module-ibc">{mod['ibc_chapter']}</div>
          </div>
        </div>
        <span class="badge {status_class}" style="font-size:13px;padding:6px 14px">{status_text}</span>
      </div>
      <table class="check-table">
        <thead>
          <tr>
            <th>Check</th><th>Formula</th><th>IBC Required</th><th>Design Actual</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          {_check_rows(mod['checks'])}
        </tbody>
      </table>
    </div>"""

def _room_rows(rooms: list) -> str:
    rows = []
    for r in rooms:
        conf_color = {"high": "#22c55e", "medium": "#f59e0b", "low": "#ef4444"}.get(r.get("confidence"), "#64748b")
        rows.append(f"""
        <tr>
          <td class="room-name-cell">{r['name']}</td>
          <td>{r.get('enclosure','—')}</td>
          <td>{r.get('capacity','—')}</td>
          <td>{r.get('area_sqft','—')}</td>
          <td class="ibc-cat">{r.get('ibc_category','—')}</td>
          <td style="font-family:monospace;font-size:12px">{r.get('load_factor','—')}</td>
          <td><span class="conf-badge" style="color:{conf_color};border-color:{conf_color}40;background:{conf_color}15">{r.get('confidence','—')}</span></td>
          <td class="mapper-tag">{r.get('mapper','—')}</td>
        </tr>
        <tr class="note-row"><td colspan="8"><span class="note">💬 {r.get('reasoning','No reasoning provided.')}</span></td></tr>""")
    return "\n".join(rows)

def generate_html(project: dict, modules: list, rooms: list) -> str:
    timestamp = datetime.now().strftime("%B %d, %Y at %H:%M")
    total_checks = sum(len(m["checks"]) for m in modules)
    scoreable = [c for m in modules for c in m["checks"] if c.get("pass") is not None]
    passed    = sum(1 for c in scoreable if c["pass"] is True)
    failed    = sum(1 for c in scoreable if c["pass"] is False)
    overall_pass = failed == 0 and len(scoreable) > 0
    overall_badge = _pass_badge(overall_pass if scoreable else None)
    pass_pct = round(passed / len(scoreable) * 100) if scoreable else 0

    module_sections = "\n".join(_module_section(m, i+1) for i, m in enumerate(modules))
    room_rows_html  = _room_rows(rooms)

    sprinkler_label = "Sprinklered ✅" if project["is_sprinklered"] else "Unsprinklered ⚠️"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{project['project_name']} · IBC Compliance Report</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: #0a0e1a; --bg2: #0f1629; --surface: #1a2340; --surface2: #202b4a;
      --border: #2a3558; --text: #e2e8f0; --muted: #64748b; --dim: #94a3b8;
      --pass: #22c55e; --fail: #ef4444; --warn: #f59e0b; --accent: #6366f1;
    }}
    @media print {{
      body {{ background: white; color: #111; }}
      .header {{ background: #1e1b4b; }}
      .module-card {{ break-inside: avoid; border: 1px solid #e2e8f0; }}
      .no-print {{ display: none; }}
    }}
    body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}

    /* ── Header ── */
    .header {{
      background: linear-gradient(135deg, #0d1b3e 0%, #1a1040 60%, #0d1b3e 100%);
      padding: 48px 48px 40px; border-bottom: 1px solid var(--border);
      display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 24px;
    }}
    .header-left {{ flex: 1; }}
    .report-badge {{
      display: inline-flex; align-items: center; gap: 6px;
      background: #6366f120; border: 1px solid #6366f150;
      color: #818cf8; font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
      text-transform: uppercase; padding: 4px 12px; border-radius: 100px; margin-bottom: 14px;
    }}
    h1 {{ font-size: 28px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 6px; }}
    h1 span {{ color: #818cf8; }}
    .header-meta {{ font-size: 12px; color: var(--muted); margin-top: 8px; }}
    .overall-badge-wrap {{ display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }}
    .score-ring {{
      width: 100px; height: 100px;
      background: conic-gradient(var(--pass) {pass_pct}%, #1e293b {pass_pct}%);
      border-radius: 50%; display: flex; align-items: center; justify-content: center;
      font-size: 22px; font-weight: 700;
    }}
    .score-label {{ font-size: 11px; color: var(--muted); text-align: center; }}

    /* ── Project Stats ── */
    .stats-bar {{
      display: flex; flex-wrap: wrap; gap: 0;
      background: var(--surface); border-bottom: 1px solid var(--border);
    }}
    .stat {{
      flex: 1; min-width: 120px; padding: 20px 24px;
      border-right: 1px solid var(--border);
    }}
    .stat:last-child {{ border-right: none; }}
    .stat-label {{ font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); margin-bottom: 4px; }}
    .stat-value {{ font-size: 22px; font-weight: 700; }}
    .stat-sub {{ font-size: 11px; color: var(--dim); margin-top: 2px; }}

    /* ── Summary Row ── */
    .summary-row {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 16px; padding: 24px 48px; background: var(--bg2);
    }}
    .sum-card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 12px; padding: 18px 20px;
    }}
    .sum-card.pass {{ border-color: var(--pass)50; background: #0b2015; }}
    .sum-card.fail {{ border-color: var(--fail)50; background: #1e0b0b; }}
    .sum-label {{ font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); margin-bottom: 4px; }}
    .sum-value {{ font-size: 28px; font-weight: 700; }}
    .sum-card.pass .sum-value {{ color: var(--pass); }}
    .sum-card.fail .sum-value {{ color: var(--fail); }}

    /* ── Section Heading ── */
    .section {{ padding: 32px 48px; }}
    .section-head {{
      display: flex; align-items: center; gap: 12px;
      font-size: 11px; font-weight: 700; letter-spacing: 0.1em;
      text-transform: uppercase; color: var(--muted);
      padding-bottom: 14px; border-bottom: 1px solid var(--border); margin-bottom: 24px;
    }}

    /* ── Module Cards ── */
    .module-card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 16px; overflow: hidden; margin-bottom: 24px;
    }}
    .module-header {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 20px 24px; border-bottom: 1px solid var(--border);
    }}
    .module-pass {{ background: linear-gradient(90deg, #0b2015, var(--surface)); border-bottom-color: var(--pass)40; }}
    .module-fail {{ background: linear-gradient(90deg, #1e0b0b, var(--surface)); border-bottom-color: var(--fail)40; }}
    .module-na  {{ background: linear-gradient(90deg, #1c1507, var(--surface)); border-bottom-color: var(--warn)40; }}
    .module-title {{ display: flex; align-items: center; gap: 14px; }}
    .module-icon {{ font-size: 24px; }}
    .module-name {{ font-size: 16px; font-weight: 700; }}
    .module-ibc  {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}

    /* ── Check Table ── */
    .check-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .check-table thead {{ background: #141d35; }}
    .check-table th {{
      padding: 10px 16px; text-align: left;
      font-size: 10px; font-weight: 700; letter-spacing: 0.08em;
      text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--border);
    }}
    .check-table td {{ padding: 12px 16px; border-bottom: 1px solid #1e2a45; vertical-align: top; }}
    .check-name {{ font-weight: 600; color: var(--text); min-width: 200px; }}
    .ibc-ref {{ font-size: 10px; color: var(--accent); margin-top: 3px; font-weight: 500; }}
    .formula {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--dim); max-width: 220px; }}
    .required {{ font-weight: 600; color: #7dd3fc; font-size: 13px; }}
    .actual {{ color: var(--text); }}
    .status {{ white-space: nowrap; }}
    .note-row td {{ padding: 4px 16px 12px; border-bottom: 1px solid var(--border); }}
    .note {{ font-size: 11px; color: var(--muted); font-style: italic; }}
    .check-table tbody tr:hover {{ background: var(--surface2); }}
    .note-row {{ background: transparent !important; }}

    /* ── Badges ── */
    .badge {{ display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }}
    .badge.pass {{ background: var(--pass)20; color: var(--pass); border: 1px solid var(--pass)40; }}
    .badge.fail {{ background: var(--fail)20; color: var(--fail); border: 1px solid var(--fail)40; }}
    .badge.na   {{ background: var(--warn)15; color: var(--warn); border: 1px solid var(--warn)40; }}

    /* ── Room Mapping Table ── */
    .room-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .room-table thead {{ background: #141d35; }}
    .room-table th {{
      padding: 10px 14px; text-align: left;
      font-size: 10px; font-weight: 700; letter-spacing: 0.08em;
      text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--border);
    }}
    .room-table td {{ padding: 10px 14px; border-bottom: 1px solid #1e2a45; vertical-align: top; font-size: 12px; }}
    .room-name-cell {{ font-weight: 600; }}
    .ibc-cat {{ font-weight: 600; color: #818cf8; }}
    .mapper-tag {{ font-size: 10px; color: var(--muted); }}
    .conf-badge {{ display: inline-block; font-size: 10px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; border: 1px solid; }}
    .table-wrap {{ overflow-x: auto; border-radius: 12px; border: 1px solid var(--border); }}

    /* ── Footer ── */
    .footer {{ text-align: center; padding: 32px; color: var(--muted); font-size: 11px; border-top: 1px solid var(--border); }}
    .print-btn {{
      position: fixed; bottom: 24px; right: 24px;
      background: var(--accent); color: white; border: none;
      padding: 12px 22px; border-radius: 10px; font-size: 14px; font-weight: 600;
      cursor: pointer; box-shadow: 0 4px 20px #6366f140; transition: all 0.2s;
    }}
    .print-btn:hover {{ background: #4f46e5; transform: translateY(-1px); }}
  </style>
</head>
<body>

  <div class="header">
    <div class="header-left">
      <div class="report-badge">⚡ Salt-Mine · IBC Compliance Report</div>
      <h1><span>{project['project_name']}</span> — Compliance Report</h1>
      <p class="header-meta">
        Generated {timestamp} &nbsp;·&nbsp; IBC 2021 &nbsp;·&nbsp; Business (B) Occupancy &nbsp;·&nbsp; {sprinkler_label}
      </p>
    </div>
    <div class="overall-badge-wrap">
      <div class="score-ring">{pass_pct}%</div>
      <div class="score-label">checks passed<br>({passed} of {len(scoreable)})</div>
    </div>
  </div>

  <div class="stats-bar">
    <div class="stat"><div class="stat-label">Floors</div><div class="stat-value">{project['num_floors']}</div><div class="stat-sub">occupied</div></div>
    <div class="stat"><div class="stat-label">Sqft / Floor</div><div class="stat-value">{project['sqft_per_floor']:,.0f}</div><div class="stat-sub">usable area</div></div>
    <div class="stat"><div class="stat-label">Total Sqft</div><div class="stat-value">{project['total_sqft']:,.0f}</div><div class="stat-sub">all floors</div></div>
    <div class="stat"><div class="stat-label">Headcount</div><div class="stat-value">{project['total_headcount']}</div><div class="stat-sub">{project['regularity']} occupancy</div></div>
    <div class="stat"><div class="stat-label">Per Floor</div><div class="stat-value">{project['headcount_per_floor']}</div><div class="stat-sub">avg occupants</div></div>
    <div class="stat"><div class="stat-label">Meeting Rooms</div><div class="stat-value">{project['num_meeting_rooms']}</div><div class="stat-sub">{project['meeting_room_capacity']} cap each</div></div>
  </div>

  <div class="summary-row">
    <div class="sum-card pass"><div class="sum-label">✅ Checks Passed</div><div class="sum-value">{passed}</div></div>
    <div class="sum-card {'fail' if failed > 0 else 'pass'}"><div class="sum-label">❌ Checks Failed</div><div class="sum-value">{failed}</div></div>
    <div class="sum-card"><div class="sum-label">⚠️ Verify from Drawings</div><div class="sum-value">{total_checks - len(scoreable)}</div></div>
    <div class="sum-card"><div class="sum-label">📋 Total Checks</div><div class="sum-value">{total_checks}</div></div>
  </div>

  <div class="section">
    <div class="section-head">📋 &nbsp; IBC Compliance Checks — 3 Modules</div>
    {module_sections}
  </div>

  <div class="section">
    <div class="section-head">🏢 &nbsp; Room / Space Mapping — AI Function of Space Assignment</div>
    <div class="table-wrap">
      <table class="room-table">
        <thead>
          <tr>
            <th>Space Name</th><th>Enclosure</th><th>Cap.</th><th>Sqft</th>
            <th>IBC Function of Space</th><th>Load Factor</th><th>Confidence</th><th>Mapper</th>
          </tr>
        </thead>
        <tbody>
          {room_rows_html}
        </tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    Salt-Mine &nbsp;·&nbsp; IBC 2021 Compliance Engine &nbsp;·&nbsp; {timestamp}<br>
    <small>This report is generated for planning and test-fit analysis purposes. Consult a licensed Architect or Code Consultant before permit submission.</small>
  </div>

  <button class="print-btn no-print" onclick="window.print()">🖨 Export to PDF</button>

</body>
</html>"""

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Salt-Mine IBC Compliance Engine")
    parser.add_argument("--demo", action="store_true", help="Run with built-in demo data")
    parser.add_argument("--ai",   action="store_true", help="Use Gemini AI for room mapping")
    args = parser.parse_args()

    ibc = load_ibc()
    project = demo_inputs() if args.demo else collect_inputs()

    print(f"\n{'═'*60}")
    print(f"  Running 3 IBC Compliance Checks for: {project['project_name']}")
    print(f"{'═'*60}")

    modules = [
        check_occupancy_load(project, ibc),
        check_plumbing(project, ibc),
        check_egress(project, ibc),
    ]

    print_results(modules)

    print(f"\n── Mapping rooms via {'AI' if args.ai else 'legacy'} mapper ──")
    rooms = get_room_mappings(project, use_ai=args.ai)

    # Save JSON results
    output = {"project": project, "timestamp": datetime.now().isoformat(), "modules": modules, "room_mappings": rooms}
    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    # Generate HTML report
    html = generate_html(project, modules, rooms)
    with open(REPORT_PATH, "w") as f:
        f.write(html)

    print(f"\n{'═'*60}")
    print(f"  ✅ compliance_results.json → {RESULTS_PATH}")
    print(f"  ✅ compliance_report.html  → {REPORT_PATH}")
    print(f"{'═'*60}")
    print(f"\n  Open report: open {REPORT_PATH}\n")

if __name__ == "__main__":
    main()
