#!/usr/bin/env python3
"""
legacy_mapper.py — Brittle Heuristic IBC Space Function Mapper
===============================================================
Simulates the existing production behavior of spaceFunctionMapper.js.
Uses keyword string-matching against room names to assign IBC categories.

This is the BASELINE to beat. It fails on creative room names like
"Mars", "The Hive", "Boiler Room", "MDF Room", etc.

Usage:
  python legacy_mapper.py                        # runs against test_cases.json
  python legacy_mapper.py --input my_blocks.json # custom input file
"""

import json
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TEST_CASES_PATH = SCRIPT_DIR / "test_cases.json"
OUTPUT_PATH = SCRIPT_DIR / "legacy_mapper_results.json"

# ─── Heuristic Rule Table ─────────────────────────────────────────────────────
# This mirrors the keyword matching logic that exists in spaceFunctionMapper.js.
# Order matters — first match wins.

HEURISTIC_RULES = [
    # Storage / Utility
    {
        "keywords": ["it closet", "server room", "storage", "supply room", "filing",
                     "boiler", "utility", "mdf", "idf", "telecom", "janitor", "mechanical"],
        "ibc_category": "Storage",
        "load_factor": 300,
        "area_method": "gross",
    },
    # Kitchens
    {
        "keywords": ["kitchen", "cafeteria", "catering", "prep kitchen", "commercial kitchen"],
        "ibc_category": "Kitchens",
        "load_factor": 200,
        "area_method": "gross",
    },
    # Mercantile
    {
        "keywords": ["showroom", "sales floor", "retail", "exhibition", "display floor", "gallery"],
        "ibc_category": "Mercantile",
        "load_factor": 60,
        "area_method": "gross",
    },
    # Classroom
    {
        "keywords": ["classroom", "computer lab", "science lab", "seminar room",
                     "instruction", "learning lab", "teaching"],
        "ibc_category": "Classroom",
        "load_factor": 20,
        "area_method": "net",
    },
    # Assembly – Concentrated (auditorium-style, high density)
    {
        "keywords": ["auditorium", "town hall", "all-hands", "all hands",
                     "amphitheater", "lecture hall", "standing"],
        "ibc_category": "Assembly – Concentrated",
        "load_factor": 7,
        "area_method": "net",
    },
    # Assembly – Unconcentrated (meeting rooms with tables)
    {
        "keywords": ["conference", "meeting", "boardroom", "war room", "breakout",
                     "collaboration", "huddle", "think tank"],
        "ibc_category": "Assembly – Unconcentrated",
        "load_factor": 15,
        "area_method": "net",
    },
    # Concentrated Business (call centers, dense ops)
    {
        "keywords": ["call center", "trading floor", "hotdesk", "operations hub",
                     "command center"],
        "ibc_category": "Concentrated Business",
        "load_factor": 50,
        "area_method": "gross",
    },
    # Breakrooms — heuristic wrongly maps to Assembly (common error)
    {
        "keywords": ["breakroom", "break room", "pantry", "lounge"],
        "ibc_category": "Assembly – Unconcentrated",
        "load_factor": 15,
        "area_method": "net",
    },
]

DEFAULT_FALLBACK = {
    "ibc_category": "Business Areas",
    "load_factor": 150,
    "area_method": "gross",
    "reasoning": "No keyword match found. Defaulted to Business Areas (legacy fallback)."
}

# ─── Core matcher ─────────────────────────────────────────────────────────────

def legacy_classify(block: dict) -> dict:
    name_lower = block.get("name", "").lower()

    for rule in HEURISTIC_RULES:
        for kw in rule["keywords"]:
            if kw in name_lower:
                return {
                    "ibc_category": rule["ibc_category"],
                    "load_factor": rule["load_factor"],
                    "area_method": rule["area_method"],
                    "confidence": "medium",
                    "reasoning": f"Keyword match: '{kw}' found in room name '{block['name']}'."
                }

    # No match — fall through to default
    return {
        **DEFAULT_FALLBACK,
        "confidence": "low",
    }

# ─── Batch runner ─────────────────────────────────────────────────────────────

def run_batch(input_path: Path = TEST_CASES_PATH, output_path: Path = OUTPUT_PATH):
    print(f"\n{'='*60}")
    print("  SALT-MINE  |  Legacy Heuristic IBC Mapper")
    print(f"  Input: {input_path.name}")
    print(f"{'='*60}\n")

    with open(input_path) as f:
        data = json.load(f)

    blocks = data.get("test_cases", data) if isinstance(data, dict) else data

    results = []
    total = len(blocks)
    correct = 0
    has_ground_truth = "expected_ibc" in blocks[0] if blocks else False

    for i, block in enumerate(blocks, 1):
        name = block.get("name", f"Block {i}")
        classification = legacy_classify(block)

        result = {
            "id": block.get("id", f"B{i:02d}"),
            "name": name,
            "enclosure": block.get("enclosure"),
            "capacity": block.get("capacity"),
            "area_sqft": block.get("area_sqft"),
            "mapper": "Legacy (Keyword Heuristic)",
            **classification
        }

        if has_ground_truth:
            expected = block.get("expected_ibc")
            result["expected_ibc"] = expected
            result["expected_load_factor"] = block.get("expected_load_factor")
            result["difficulty"] = block.get("difficulty", "medium")
            result["correct"] = (classification["ibc_category"] == expected)
            if result["correct"]:
                correct += 1
            status = "✅" if result["correct"] else "❌"
            print(f"[{i:02d}/{total}] '{name}' → {status} {classification['ibc_category']} (expected: {expected})")
        else:
            print(f"[{i:02d}/{total}] '{name}' → {classification['ibc_category']}")

        results.append(result)

    output = {
        "mapper": "Legacy (Keyword Heuristic)",
        "total": total,
        "results": results
    }

    if has_ground_truth:
        accuracy = correct / total * 100
        output["correct"] = correct
        output["accuracy_pct"] = round(accuracy, 1)
        print(f"\n{'='*60}")
        print(f"  LEGACY MAPPER ACCURACY: {correct}/{total} = {accuracy:.1f}%")
        print(f"{'='*60}\n")

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Results saved → {output_path}\n")
    return output

# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Legacy heuristic IBC Space Function Mapper")
    parser.add_argument("--input", type=Path, default=TEST_CASES_PATH,
                        help="Input JSON file (default: test_cases.json)")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH,
                        help="Output JSON file (default: legacy_mapper_results.json)")
    args = parser.parse_args()
    run_batch(input_path=args.input, output_path=args.output)

if __name__ == "__main__":
    main()
