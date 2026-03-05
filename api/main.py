#!/usr/bin/env python3
"""
api/main.py — Salt-Mine IBC Compliance FastAPI Backend
=======================================================
Gemini-powered IBC compliance engine exposed as a REST API.
All IBC knowledge (occupancy, plumbing, egress) is embedded in the
Gemini system prompt — no database required.

Endpoints:
  POST /api/compliance   — Full compliance check + room mapping
  POST /api/classify     — Classify a single room
  GET  /api/ibc-rules    — Return the IBC rules config as JSON
  GET  /api/health       — Health check
"""

import os
import json
import math
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Annotated
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import google.generativeai as genai

# ── Load env ──────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent.parent
load_dotenv(BASE / ".env")

API_KEY    = os.environ.get("GEMINI_API_KEY", "")
IBC_PATH   = BASE / "ibc_rules.json"
MODEL_NAME = "gemini-2.0-flash"

# ── Load IBC config ───────────────────────────────────────────────────────────
with open(IBC_PATH) as f:
    IBC_RULES = json.load(f)

# ── Build rich IBC system prompt ──────────────────────────────────────────────
def _build_category_block() -> str:
    lines = []
    for cat in IBC_RULES["categories"]:
        lines.append(
            f"• **{cat['category']}** | Load Factor: {cat['load_factor']} sq ft/person ({cat['area_method'].upper()})\n"
            f"  Desc: {cat['description']}\n"
            f"  Typical enclosure: {cat['enclosure_hint']} | Density: {cat['density_hint']}\n"
            f"  Disqualifiers: {'; '.join(cat['disqualifiers'])}"
        )
    return "\n\n".join(lines)

IBC_SYSTEM_PROMPT = f"""
You are an expert IBC (International Building Code) compliance analyst. 
You are performing a comprehensive audit based on IBC 2021, focusing heavily on Chapters 7, 8, 9, and 10.

## YOUR ROLE
Analyze building parameters and space mappings to identify non-compliance. You must classify issues into:
- CRITICAL: Life safety violations (Egress, Occupancy Load, Required Exits).
- WARNING: Infrastructure requirements (Sprinklers, Elevators, Fire ratings).
- ADVISORY: Best practices or interior finish requirements (IBC Chapter 8).

## IBC REFERENCE: KEY CHAPTERS
- **Chapter 7**: Fire and Smoke Protection Features (Ratings for corridors, shafts).
- **Chapter 8**: Interior Finishes (Flame spread index, smoke-developed index).
- **Chapter 9**: Fire Protection Systems (Sprinklers required for B-occupancy > 12,000 sqft or 3+ stories).
- **Chapter 10**: Means of Egress (Occupant Load, Exits, Widths).

## IBC REFERENCE: PLUMBING (Table 2902.1)
- Water Closets: 1 per 50 male, 1 per 25 female.
- Lavatories: 1 per 40.

## OUTPUT FORMAT (strict JSON, no markdown fences)
For room mapping, return:
{{
  "ibc_category": "<exact category name>",
  "load_factor": <integer>,
  "confidence": "<high|medium|low>",
  "reasoning": "<brief CoT>"
}}
"""

# ── Gemini client ─────────────────────────────────────────────────────────────
_model = None

def get_model():
    global _model
    if _model is None:
        if not API_KEY:
            raise HTTPException(500, "GEMINI_API_KEY not set in environment")
        genai.configure(api_key=API_KEY)
        _model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=IBC_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json",
            )
        )
    return _model

# ── Pydantic models ───────────────────────────────────────────────────────────

class RoomInput(BaseModel):
    name: str
    enclosure: str = "Open"
    capacity: int = 0
    area_sqft: float = 0.0

class FloorInput(BaseModel):
    floor_id: int
    sqft: float
    permanent_occupancy: int
    temporary_occupancy: int

class ProjectInput(BaseModel):
    project_name: str = "My Project"
    num_floors: int = Field(ge=1, le=100)
    sqft_per_floor: float = Field(ge=1)
    primary_building_type: str = "Business (B)"
    permanent_occupancy: int = Field(ge=0, default=0)
    temporary_occupancy: int = Field(ge=0, default=0)
    total_headcount: int = 0
    male_pct: int = Field(ge=0, le=100, default=50)
    is_sprinklered: bool = True
    num_meeting_rooms: int = Field(ge=0, default=0)
    meeting_room_capacity: int = Field(ge=0, default=10)
    rooms: Optional[List[RoomInput]] = None
    floors_data: List[FloorInput] = []
    # Actual design values (Optional inputs)
    actual_exits_per_floor: Optional[int] = None
    actual_wc_male_per_floor: Optional[int] = None
    actual_wc_female_per_floor: Optional[int] = None
    actual_lavatories_per_floor: Optional[int] = None
    actual_drinking_fountains: Optional[int] = None
    actual_service_sinks: Optional[int] = None

# Rebuild models for Pydantic V2 to resolve resolution issues
ProjectInput.model_rebuild()

# ── IBC computation engines ───────────────────────────────────────────────────

def compute_occupancy_load(p: ProjectInput) -> dict:
    load_factor = 150
    sqft = p.sqft_per_floor
    occ_per_floor = math.ceil(p.total_headcount / p.num_floors)
    meeting_rooms_per_floor = max(1, math.ceil(p.num_meeting_rooms / p.num_floors)) if p.num_meeting_rooms else 0
    meeting_sqft_pf = meeting_rooms_per_floor * 300
    office_sqft = max(sqft - meeting_sqft_pf, sqft * 0.6)
    allowed_office  = math.floor(office_sqft / load_factor)
    allowed_meeting = math.floor(meeting_sqft_pf / 15) if meeting_sqft_pf else 0
    allowed_total   = allowed_office + allowed_meeting
    meeting_peak_pf = meeting_rooms_per_floor * p.meeting_room_capacity if p.num_meeting_rooms else 0
    actual_total    = occ_per_floor + meeting_peak_pf

    def chk(label, ref, formula, req_val, req_str, act_val, act_str, note):
        return {"check": label, "ibc_ref": ref, "formula": formula,
                "required": req_str, "required_val": req_val,
                "actual": act_str, "actual_val": act_val,
                "pass": act_val <= req_val, "note": note}

    checks = [
        chk("Max Occupancy — Office Areas", "IBC Table 1004.5",
            f"{office_sqft:,.0f} sqft ÷ {load_factor} sqft/person",
            allowed_office, f"≤ {allowed_office} persons",
            occ_per_floor, f"{occ_per_floor} persons/floor",
            "Business Areas load factor 150 gross sqft/person"),
        chk("Max Occupancy — Meeting Rooms", "IBC Table 1004.5",
            f"{meeting_sqft_pf:,.0f} sqft ÷ 15 sqft/person (Assembly–Uncon.)",
            allowed_meeting, f"≤ {allowed_meeting} persons",
            meeting_peak_pf, f"{meeting_peak_pf} persons (peak)",
            "Assembly–Unconcentrated load factor 15 net sqft/person") if meeting_sqft_pf else None,
        chk("Combined Floor Occupancy", "IBC 1004.8",
            f"Office {allowed_office} + Meeting {allowed_meeting}",
            allowed_total, f"≤ {allowed_total} persons/floor",
            actual_total, f"{actual_total} persons/floor (peak)",
            "Combined peak load per floor (all rooms simultaneously occupied)"),
    ]
    checks = [c for c in checks if c]
    return {
        "module": "Occupancy Load", "ibc_chapter": "IBC Chapter 10 — Table 1004.5",
        "overall_pass": all(c["pass"] for c in checks), "checks": checks,
        "summary": {"sqft_per_floor": sqft, "load_factor_office": load_factor,
                    "allowed_per_floor": allowed_total, "actual_per_floor": actual_total}
    }

def compute_plumbing(p: ProjectInput) -> dict:
    pt = IBC_RULES["plumbing_table"]["fixtures"]
    occ = math.ceil(p.total_headcount / p.num_floors)
    male_occ   = math.ceil(occ * p.male_pct / 100)
    female_occ = occ - male_occ

    def req(val, ratio, minimum): return max(math.ceil(val / ratio), minimum)
    def actual_val(v): return v if v is not None else None
    def actual_str(v): return f"{v} provided" if v is not None else "Not provided"
    def chk_val(act, req_v): return act >= req_v if act is not None else None

    checks = [
        {"check": "Water Closets — Male (per floor)", "ibc_ref": "IBC Table 2902.1",
         "formula": f"⌈{male_occ} male ÷ 50⌉",
         "required": f"≥ {req(male_occ, 50, 1)} WC(s)", "required_val": req(male_occ, 50, 1),
         "actual": actual_str(p.actual_wc_male_per_floor), "actual_val": actual_val(p.actual_wc_male_per_floor),
         "pass": chk_val(p.actual_wc_male_per_floor, req(male_occ, 50, 1)),
         "note": "IBC 2902.1: 1 WC per 50 male occupants, Business (B) occupancy"},
        {"check": "Water Closets — Female (per floor)", "ibc_ref": "IBC Table 2902.1",
         "formula": f"⌈{female_occ} female ÷ 25⌉",
         "required": f"≥ {req(female_occ, 25, 1)} WC(s)", "required_val": req(female_occ, 25, 1),
         "actual": actual_str(p.actual_wc_female_per_floor), "actual_val": actual_val(p.actual_wc_female_per_floor),
         "pass": chk_val(p.actual_wc_female_per_floor, req(female_occ, 25, 1)),
         "note": "IBC 2902.1: 1 WC per 25 female occupants, Business (B) occupancy"},
        {"check": "Lavatories / Sinks (per floor)", "ibc_ref": "IBC Table 2902.1",
         "formula": f"⌈{occ} occ ÷ 40⌉",
         "required": f"≥ {req(occ, 40, 1)}", "required_val": req(occ, 40, 1),
         "actual": actual_str(p.actual_lavatories_per_floor), "actual_val": actual_val(p.actual_lavatories_per_floor),
         "pass": chk_val(p.actual_lavatories_per_floor, req(occ, 40, 1)),
         "note": "IBC 2902.1: 1 lavatory per 40 occupants"},
        {"check": "Drinking Fountains (whole building)", "ibc_ref": "IBC Table 2902.1",
         "formula": f"⌈{p.total_headcount} total ÷ 100⌉",
         "required": f"≥ {req(p.total_headcount, 100, 1)}", "required_val": req(p.total_headcount, 100, 1),
         "actual": actual_str(p.actual_drinking_fountains), "actual_val": actual_val(p.actual_drinking_fountains),
         "pass": chk_val(p.actual_drinking_fountains, req(p.total_headcount, 100, 1)),
         "note": "IBC 2902.1: 1 per 100 occupants; ADA requires accessible + standard height"},
        {"check": "Service Sinks (whole building)", "ibc_ref": "IBC Table 2902.1",
         "formula": f"1 per floor × {p.num_floors} floors",
         "required": f"≥ {p.num_floors} service sink(s)", "required_val": p.num_floors,
         "actual": actual_str(p.actual_service_sinks), "actual_val": actual_val(p.actual_service_sinks),
         "pass": chk_val(p.actual_service_sinks, p.num_floors),
         "note": "IBC 2902.1: Minimum 1 service sink per floor"},
    ]
    scoreable = [c for c in checks if c["pass"] is not None]
    return {
        "module": "Plumbing", "ibc_chapter": "IBC Chapter 29 — Table 2902.1",
        "overall_pass": all(c["pass"] for c in scoreable) if scoreable else None,
        "checks": checks,
        "summary": {"occupants_per_floor": occ, "male": male_occ, "female": female_occ}
    }

def compute_egress(p: ProjectInput) -> dict:
    et = IBC_RULES["egress_table"]
    occ = math.ceil(p.total_headcount / p.num_floors)
    req_exits = next(t["min_exits"] for t in et["exit_count_thresholds"] if occ <= t["max_occupants"])
    door_min  = et["door_width"]["minimum_clear_inches"]
    req_door  = max(round(occ * et["door_width"]["factor_inches_per_occupant"], 1), door_min)
    req_corr  = et["corridor_width"]["over_49_occupants_inches"] if occ > 49 else et["corridor_width"]["under_50_occupants_inches"]
    travel    = et["travel_distance"]["sprinklered_ft"] if p.is_sprinklered else et["travel_distance"]["unsprinklered_ft"]
    stair_min = et["stair_width"]["minimum_inches"]
    req_stair = max(round(occ * et["stair_width"]["factor_inches_per_occupant"], 1), stair_min)
    sp_label  = "sprinklered" if p.is_sprinklered else "unsprinklered"

    def exits_pass(act, req): return act >= req if act is not None else None
    act_exits = p.actual_exits_per_floor

    checks = [
        {"check": "Number of Exits (per floor)", "ibc_ref": "IBC 1006.3",
         "formula": f"{occ} occ/floor → threshold lookup",
         "required": f"≥ {req_exits} exit(s)", "required_val": req_exits,
         "actual": f"{act_exits} exit(s) provided" if act_exits is not None else "Not provided",
         "actual_val": act_exits,
         "pass": exits_pass(act_exits, req_exits),
         "note": f"IBC 1006.3: {occ} occupants requires ≥{req_exits} exit(s)"},
        {"check": "Exit Door Clear Width", "ibc_ref": "IBC 1005.1",
         "formula": f"{occ} occ × 0.2 in = {occ*0.2:.1f}\" (min {door_min}\")",
         "required": f"≥ {req_door}\" clear width", "required_val": req_door,
         "actual": "Verify from drawings", "actual_val": None, "pass": None,
         "note": "IBC 1005.1: 0.2 in/occupant, never less than 32\" clear"},
        {"check": "Corridor Minimum Width", "ibc_ref": "IBC 1005.1",
         "formula": f"{occ} occ/floor → {'44\"' if occ > 49 else '36\"'} minimum",
         "required": f"≥ {req_corr}\" wide", "required_val": req_corr,
         "actual": "Verify from drawings", "actual_val": None, "pass": None,
         "note": f"IBC 1005.1: 44\" min if >49 occupants, 36\" if ≤49"},
        {"check": "Max Travel Distance to Exit", "ibc_ref": "IBC 1017.2",
         "formula": f"Business B, {sp_label} → {travel} ft limit",
         "required": f"≤ {travel} ft", "required_val": travel,
         "actual": "Verify from drawings", "actual_val": None, "pass": None,
         "note": f"IBC 1017.2: Business B {sp_label}: {travel} ft maximum travel distance"},
        {"check": "Stair Minimum Width", "ibc_ref": "IBC 1005.1",
         "formula": f"{occ} occ × 0.3 in = {occ*0.3:.1f}\" (min {stair_min}\")",
         "required": f"≥ {req_stair}\" stair width", "required_val": req_stair,
         "actual": "Verify from drawings", "actual_val": None, "pass": None,
         "note": "IBC 1005.1: 0.3 in/occupant, never less than 44\""},
    ]
    scoreable = [c for c in checks if c["pass"] is not None]
    return {
        "module": "Egress", "ibc_chapter": "IBC Chapter 10 — Sections 1005.1, 1006, 1017",
        "overall_pass": all(c["pass"] for c in scoreable) if scoreable else None,
        "checks": checks,
        "summary": {"occupants_per_floor": occ, "required_exits": req_exits,
                    "req_door_width_in": req_door, "req_corridor_in": req_corr,
                    "max_travel_ft": travel, "req_stair_in": req_stair}
    }

def compute_advanced_findings(p: ProjectInput) -> list:
    findings = []
    
    # Terminology pivot: "designs" instead of "drawings"
    VERIFY_SOURCE = "Verify from designs"
    
    # Normalize floor data
    floors = p.floors_data if p.floors_data else [
        FloorInput(
            floor_id=i+1, 
            sqft=p.sqft_per_floor, 
            permanent_occupancy=math.ceil(p.permanent_occupancy / p.num_floors),
            temporary_occupancy=math.ceil(p.temporary_occupancy / p.num_floors)
        ) for i in range(p.num_floors)
    ]

    total_sqft = sum(f.sqft for f in floors)

    for floor in floors:
        f_name = f"Floor {floor.floor_id}" if p.num_floors > 1 else ""
        prefix = f"{f_name}: " if f_name else ""
        occ = floor.permanent_occupancy + floor.temporary_occupancy

        # --- CHAPTER 7: FIRE AND SMOKE PROTECTION ---

        # 1. Fire Partitions - Corridor Ratings (IBC 708.1)
        findings.append({
            "severity": "CRITICAL", "ref": "IBC 708.1", "category": "Fire Protection",
            "issue": f"{prefix}Corridor Fire Partitions",
            "description": "Corridors in Group B often require 1-hour fire-resistance ratings.",
            "current": VERIFY_SOURCE, "required": "1-Hour Fire-Resistance Rating"
        })

        # 2. Smoke Barriers (IBC 709.1)
        if floor.sqft > 22500:
            findings.append({
                "severity": "WARNING", "ref": "IBC 709.1", "category": "Fire Protection",
                "issue": f"{prefix}Smoke Barrier Requirement",
                "description": "Large floor plates may require smoke barrier separation.",
                "current": f"{floor.sqft:,.0f} sqft", "required": "Smoke barrier partition"
            })

        # 3. Fire-resistance of Members (IBC 703.2)
        findings.append({
            "severity": "WARNING", "ref": "IBC 703.2", "category": "Construction",
            "issue": f"{prefix}Structural Fire Resistance",
            "description": "Primary structural frame must meet fire-resistance ratings based on construction type.",
            "current": VERIFY_SOURCE, "required": "UL/GA Rated Assemblies"
        })

        # 4. Penetration Firestopping (IBC 714.4.1)
        findings.append({
            "severity": "CRITICAL", "ref": "IBC 714.4.1", "category": "Fire Protection",
            "issue": f"{prefix}Through-Penetration Firestopping",
            "description": "All penetrations through fire-rated walls must be sealed with approved systems.",
            "current": VERIFY_SOURCE, "required": "ASTM E814 / UL 1479 System"
        })

        # 5. Shaft Enclosures (IBC 713.4)
        findings.append({
            "severity": "CRITICAL", "ref": "IBC 713.4", "category": "Fire Protection",
            "issue": f"{prefix}Shaft Partitioning",
            "description": "Vertical openings (stairs/elevators) require fire-rated shaft enclosures.",
            "current": VERIFY_SOURCE, "required": "2-Hour Protection (4+ stories)"
        })

        # 6. Draftstopping (IBC 718.3)
        if not p.is_sprinklered:
            findings.append({
                "severity": "ADVISORY", "ref": "IBC 718.3", "category": "Fire Protection",
                "issue": f"{prefix}Ceiling Draftstopping",
                "description": "Concealed spaces in floor/ceiling assemblies may require draftstopping.",
                "current": "Non-sprinklered design", "required": "Draftstopping every 3,000 sqft"
            })

        # 7. Fire/Smoke Dampers (IBC 717.2)
        findings.append({
            "severity": "WARNING", "ref": "IBC 717.2", "category": "Fire Protection",
            "issue": f"{prefix}Plenum Fire Dampers",
            "description": "Duct penetrations of fire-rated walls require automated fire/smoke dampers.",
            "current": VERIFY_SOURCE, "required": "UL 555 Rated Dampers"
        })

        # --- CHAPTER 8: INTERIOR FINISHES ---

        # 8. Wall and Ceiling Finishes (IBC 803.1.1)
        findings.append({
            "severity": "CRITICAL", "ref": "IBC 803.1.1", "category": "Finishes",
            "issue": f"{prefix}Flame Spread Index",
            "description": "Corridor finishes in Group B must meet Class A or B requirements.",
            "current": VERIFY_SOURCE, "required": "Class A (Flame Spread 0-25)"
        })

        # 9. Floor Finish Radiance (IBC 804.4.1)
        findings.append({
            "severity": "WARNING", "ref": "IBC 804.4.1", "category": "Finishes",
            "issue": f"{prefix}Critical Radiant Flux",
            "description": "Floor finishes in exits and corridors require Class I or II radiance rating.",
            "current": VERIFY_SOURCE, "required": "≥ 0.45 W/cm² (Class I)"
        })

        # 10. Decorative Materials (IBC 806.7)
        findings.append({
            "severity": "ADVISORY", "ref": "IBC 806.7", "category": "Finishes",
            "issue": f"{prefix}Decorative Trim Limits",
            "description": "Combustible decorative trim is limited to 10% of specific wall/ceiling areas.",
            "current": VERIFY_SOURCE, "required": "≤ 10% Aggregate Area"
        })

        # 11. Acoustical Ceiling Systems (IBC 808.1.1)
        findings.append({
            "severity": "ADVISORY", "ref": "IBC 808.1.1", "category": "Finishes",
            "issue": f"{prefix}Suspended Ceiling Supports",
            "description": "Acoustical ceiling grids must be designed for fire safety and seismic stability.",
            "current": VERIFY_SOURCE, "required": "ASTM C635 / C636 Compliance"
        })

        # 12. Site-fabricated Stretch Systems (IBC 803.15)
        findings.append({
            "severity": "WARNING", "ref": "IBC 803.15", "category": "Finishes",
            "issue": f"{prefix}Stretch Ceiling Fire Safety",
            "description": "Textile wall/ceiling systems must be tested per NFPA 286.",
            "current": VERIFY_SOURCE, "required": "Pass NFPA 286 Criteria"
        })

    return findings

async def classify_room_ai(room: RoomInput) -> dict:
    model  = get_model()
    area   = room.area_sqft
    cap    = room.capacity
    density = f"{area/cap:.1f} sqft/person" if cap > 0 else "N/A (zero occupancy)"
    prompt = (
        f"Room Name: {room.name}\n"
        f"Enclosure: {room.enclosure}\n"
        f"Capacity: {cap} people\n"
        f"Area: {area} sqft\n"
        f"Density: {density}\n\n"
        "Classify this room into exactly one IBC occupancy category."
    )
    resp = model.generate_content(prompt)
    raw  = resp.text.strip().lstrip("```json").rstrip("```").strip()
    result = json.loads(raw)
    return {**room.model_dump(), **result, "mapper": f"Gemini ({MODEL_NAME})"}

def classify_room_legacy(room: RoomInput) -> dict:
    """Fallback keyword heuristic if AI is unavailable."""
    name = room.name.lower()
    rules = [
        (["it closet","server","storage","supply","filing","boiler","utility","mdf","idf","janitor"],
         "Storage", 300, "gross"),
        (["kitchen","cafeteria","catering"], "Kitchens", 200, "gross"),
        (["showroom","sales floor","retail","exhibition","display","gallery"], "Mercantile", 60, "gross"),
        (["classroom","computer lab","science lab","seminar","learning lab","teaching"], "Classroom", 20, "net"),
        (["auditorium","town hall","all-hands","amphitheater","lecture"], "Assembly – Concentrated", 7, "net"),
        (["conference","meeting","boardroom","war room","breakout","think tank","collaboration"],
         "Assembly – Unconcentrated", 15, "net"),
        (["call center","trading floor","hotdesk","command center"], "Concentrated Business", 50, "gross"),
        (["breakroom","pantry","lounge"], "Assembly – Unconcentrated", 15, "net"),
    ]
    for keywords, cat, lf, method in rules:
        if any(k in name for k in keywords):
            return {**room.model_dump(), "ibc_category": cat, "load_factor": lf,
                    "area_method": method, "confidence": "medium",
                    "reasoning": f"Keyword match in '{room.name}'.", "mapper": "Legacy (fallback)"}
    return {**room.model_dump(), "ibc_category": "Business Areas", "load_factor": 150,
            "area_method": "gross", "confidence": "low",
            "reasoning": "No keyword match — defaulted to Business Areas.", "mapper": "Legacy (fallback)"}

# ── FastAPI app ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm the Gemini model on startup
    if API_KEY:
        try:
            get_model()
            print(f"✅ Gemini model ready: {MODEL_NAME}")
        except Exception as e:
            print(f"⚠️  Gemini warm-up failed: {e}")
    yield

app = FastAPI(title="Salt-Mine IBC Compliance API", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve Frontend ────────────────────────────────────────────────────────────
@app.get("/")
async def serve_index():
    return FileResponse(BASE / "frontend" / "index.html")

@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "api_key_set": bool(API_KEY)}

@app.get("/api/ibc-rules")
def get_ibc_rules():
    return IBC_RULES

@app.post("/api/classify")
async def classify_single(room: RoomInput):
    try:
        return await classify_room_ai(room)
    except Exception as e:
        return classify_room_legacy(room)

@app.post("/api/compliance")
async def run_compliance(p: ProjectInput):
    try:
        # Calculate total headcount for internal logic
        total_headcount = p.permanent_occupancy + p.temporary_occupancy
        
        # We'll monkey-patch p with total_headcount or pass it explicitly to helpers.
        # To avoid changing all helper signatures, let's inject it into a temporary object or just use a local ref.
        # Actually, adding 'total_headcount' to the object dynamcially is easiest or just modifying helpers.
        # Let's just create a shared context or update the helpers to take total_headcount.
        
        # For simplicity, I'll add total_headcount to the p object so helpers continue to work
        setattr(p, 'total_headcount', total_headcount)

        # 1. Advanced Findings (IBC 7, 8, 9, 10)
        findings = compute_advanced_findings(p)

        # 2. Traditional Compliance Modules
        modules = [
            compute_occupancy_load(p),
            compute_plumbing(p),
            compute_egress(p),
        ]

        # 3. AI room mapping
        rooms_to_classify = p.rooms or []
        # ... rest of the room classification logic remains similar ...
        if not rooms_to_classify:
            per_floor = max(1, p.num_meeting_rooms // p.num_floors) if p.num_meeting_rooms else 0
            for i in range(1, p.num_meeting_rooms + 1):
                rooms_to_classify.append(RoomInput(
                    name=f"Meeting Room {i}", enclosure="Closed",
                    capacity=p.meeting_room_capacity, area_sqft=300))
            for i in range(1, p.num_floors + 1):
                rooms_to_classify.append(RoomInput(
                    name=f"Open Office — Floor {i}", enclosure="Open",
                    capacity=math.ceil(total_headcount / p.num_floors * 0.8),
                    area_sqft=int(p.sqft_per_floor * 0.7)))

        room_results = []
        for room in rooms_to_classify:
            try:
                result = await classify_room_ai(room)
            except Exception:
                result = classify_room_legacy(room)
            room_results.append(result)

        # 4. Score summary
        all_checks = [c for m in modules for c in m["checks"]]
        scoreable  = [c for c in all_checks if c.get("pass") is not None]
        passed     = sum(1 for c in scoreable if c["pass"] is True)
        failed     = sum(1 for c in scoreable if c["pass"] is False)

        return {
            "project": p.model_dump(),
            "timestamp": datetime.now().isoformat(),
            "findings": findings,
            "summary": {
                "total_checks": len(all_checks),
                "scoreable": len(scoreable),
                "passed": passed,
                "failed": failed,
                "na": len(all_checks) - len(scoreable),
                "pass_pct": round(passed / len(scoreable) * 100) if scoreable else 0,
                "overall_pass": failed == 0 and len(scoreable) > 0,
                "critical_count": sum(1 for f in findings if f["severity"] == "CRITICAL"),
                "warning_count": sum(1 for f in findings if f["severity"] == "WARNING"),
                "advisory_count": sum(1 for f in findings if f["severity"] == "ADVISORY"),
            },
            "modules": modules,
            "room_mappings": room_results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
