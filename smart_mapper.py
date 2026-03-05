#!/usr/bin/env python3
"""
smart_mapper.py — AI-powered IBC Space Function Mapper
=======================================================
Uses Gemini 2.0 Flash to classify real estate block instances into
IBC occupancy categories via contextual chain-of-thought reasoning.

Usage:
  python smart_mapper.py                        # runs against test_cases.json
  python smart_mapper.py --input my_blocks.json # custom input file
  python smart_mapper.py --single               # classify a single room interactively

Requirements:
  pip install google-generativeai
  export GEMINI_API_KEY="your-key-here"
"""

import os
import json
import time
import argparse
import sys
from pathlib import Path

try:
    import google.generativeai as genai
except ImportError:
    print("[ERROR] google-generativeai not installed. Run: pip install google-generativeai")
    sys.exit(1)

# ─── Config ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
IBC_RULES_PATH = SCRIPT_DIR / "ibc_rules.json"
TEST_CASES_PATH = SCRIPT_DIR / "test_cases.json"
OUTPUT_PATH = SCRIPT_DIR / "smart_mapper_results.json"

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.0-flash"

# ─── Load IBC Rules ───────────────────────────────────────────────────────────

def load_ibc_rules() -> dict:
    with open(IBC_RULES_PATH) as f:
        return json.load(f)

def build_ibc_rules_block(rules: dict) -> str:
    """Render IBC rules as a compact reference table for the system prompt."""
    lines = []
    for cat in rules["categories"]:
        lines.append(
            f"- **{cat['category']}** | Load Factor: {cat['load_factor']} sq ft/person | "
            f"Method: {cat['area_method'].upper()} | "
            f"Typical enclosure: {cat['enclosure_hint'].title()} | "
            f"Typical density: {cat['density_hint'].title()}\n"
            f"  Description: {cat['description']}\n"
            f"  Disqualifiers: {'; '.join(cat['disqualifiers'])}"
        )
    return "\n\n".join(lines)

# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """
You are an expert IBC (International Building Code) occupancy classifier for real estate test-fit analysis.

Your ONLY job is to classify a given room/space into exactly one of the 8 IBC occupancy categories below,
based on the room's name, enclosure type, capacity, area, and calculated density.

## THE 8 VALID IBC CATEGORIES (these are your ONLY valid output choices):

{ibc_rules}

## CLASSIFICATION RULES

1. **Never invent a new category.** You MUST output exactly one of the 8 category names above, verbatim.
2. **Creative names are common.** Rooms like "Mars", "Orion", "The Hive", "Boiler Room" are real examples.
   Do NOT rely on keywords alone — infer from ALL signals: name, enclosure, capacity, area, and density.
3. **Density = Area ÷ Capacity.** Low density (>100 sq ft/person) = sparse. High density (<30 sq ft/person) = packed.
4. **Enclosure is a key signal:** Closed small rooms = likely meeting rooms (Assembly–Unconcentrated).
   Open large spaces = likely office or concentrated business.
5. **Storage edge case:** Zero or near-zero capacity + small closed room = Storage, not Business.
6. **Breakrooms ≠ Kitchens:** A breakroom with a microwave is NOT a Kitchen (IBC). Only commercial food prep counts.
7. **Confidence levels:**
   - "high" = strong alignment across multiple signals
   - "medium" = most signals match, one ambiguous
   - "low" = name is misleading or signals conflict; judgement call

## OUTPUT FORMAT (strict JSON, no markdown fences, no explanation outside the JSON)

{{
  "ibc_category": "<exact category name from the 8 above>",
  "load_factor": <integer, matching the chosen category>,
  "area_method": "<gross or net>",
  "confidence": "<high|medium|low>",
  "reasoning": "<2-4 sentences of chain-of-thought explaining exactly why you chose this category and not others>"
}}
""".strip()

# ─── Gemini Client ────────────────────────────────────────────────────────────

def get_model(rules: dict):
    if not API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable not set.\n"
            "Export it with: export GEMINI_API_KEY='your-key-here'"
        )
    genai.configure(api_key=API_KEY)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        ibc_rules=build_ibc_rules_block(rules)
    )
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.1,          # low temp for deterministic classification
            response_mime_type="application/json",
        )
    )
    return model

# ─── Per-Room Classification ──────────────────────────────────────────────────

def build_user_prompt(block: dict) -> str:
    area = block.get("area_sqft", 0)
    capacity = block.get("capacity", 0)
    if capacity > 0:
        density = f"{area / capacity:.1f} sq ft/person"
    else:
        density = "N/A (zero or unknown occupancy)"

    return (
        f"Room Name: {block.get('name', 'Unknown')}\n"
        f"Enclosure: {block.get('enclosure', 'Unknown')}\n"
        f"Capacity: {capacity} people\n"
        f"Area: {area} sq ft\n"
        f"Density: {density}\n\n"
        f"Classify this room into exactly one IBC category."
    )

def classify_block(model, block: dict, retries: int = 3) -> dict:
    prompt = build_user_prompt(block)
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()
            # Strip markdown fences if model ignores mime type
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:])
            if raw.endswith("```"):
                raw = "\n".join(raw.split("\n")[:-1])
            result = json.loads(raw)
            # Validate required fields
            required = {"ibc_category", "load_factor", "area_method", "confidence", "reasoning"}
            if not required.issubset(result.keys()):
                raise ValueError(f"Missing fields: {required - result.keys()}")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  [WARN] Attempt {attempt+1} parse error for '{block.get('name')}': {e}")
            time.sleep(1)
        except Exception as e:
            print(f"  [WARN] Attempt {attempt+1} API error for '{block.get('name')}': {e}")
            time.sleep(2)
    # Fallback if all retries fail
    return {
        "ibc_category": "Business Areas",
        "load_factor": 150,
        "area_method": "gross",
        "confidence": "low",
        "reasoning": "Classification failed after retries. Defaulted to Business Areas as safest fallback."
    }

# ─── Batch Processing ─────────────────────────────────────────────────────────

def run_batch(input_path: Path = TEST_CASES_PATH, output_path: Path = OUTPUT_PATH):
    print(f"\n{'='*60}")
    print("  SALT-MINE  |  AI IBC Space Function Mapper")
    print(f"  Model: {MODEL_NAME}")
    print(f"  Input: {input_path.name}")
    print(f"{'='*60}\n")

    rules = load_ibc_rules()
    model = get_model(rules)

    with open(input_path) as f:
        data = json.load(f)

    # Support both test_cases.json format and raw block arrays
    blocks = data.get("test_cases", data) if isinstance(data, dict) else data

    results = []
    total = len(blocks)
    correct = 0
    has_ground_truth = "expected_ibc" in blocks[0] if blocks else False

    for i, block in enumerate(blocks, 1):
        name = block.get("name", f"Block {i}")
        print(f"[{i:02d}/{total}] Classifying: '{name}'")

        classification = classify_block(model, block)

        result = {
            "id": block.get("id", f"B{i:02d}"),
            "name": name,
            "enclosure": block.get("enclosure"),
            "capacity": block.get("capacity"),
            "area_sqft": block.get("area_sqft"),
            "mapper": "AI (Gemini 2.0 Flash)",
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
            print(
                f"   → {status} {classification['ibc_category']} "
                f"(expected: {expected}) | confidence: {classification['confidence']}"
            )
        else:
            print(f"   → {classification['ibc_category']} | confidence: {classification['confidence']}")

        results.append(result)
        # Small delay to avoid rate limits
        time.sleep(0.5)

    # Summary
    output = {
        "mapper": "AI (Gemini 2.0 Flash)",
        "model": MODEL_NAME,
        "total": total,
        "results": results
    }

    if has_ground_truth:
        accuracy = correct / total * 100
        output["correct"] = correct
        output["accuracy_pct"] = round(accuracy, 1)
        print(f"\n{'='*60}")
        print(f"  AI MAPPER ACCURACY: {correct}/{total} = {accuracy:.1f}%")
        print(f"{'='*60}\n")

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Results saved → {output_path}\n")
    return output

# ─── Interactive Single-Room Mode ─────────────────────────────────────────────

def run_interactive():
    rules = load_ibc_rules()
    model = get_model(rules)

    print("\n=== INTERACTIVE CLASSIFIER ===")
    print("Enter room details below (Ctrl+C to quit)\n")

    while True:
        try:
            name = input("Room Name: ").strip()
            enclosure = input("Enclosure (Open/Closed): ").strip()
            capacity = int(input("Capacity (people): ").strip())
            area = float(input("Area (sq ft): ").strip())

            block = {"name": name, "enclosure": enclosure, "capacity": capacity, "area_sqft": area}
            result = classify_block(model, block)

            print(f"\n─── RESULT ───────────────────────────────")
            print(f"  IBC Category : {result['ibc_category']}")
            print(f"  Load Factor  : {result['load_factor']} sq ft/person ({result['area_method'].upper()})")
            print(f"  Confidence   : {result['confidence']}")
            print(f"  Reasoning    :\n    {result['reasoning']}")
            print(f"──────────────────────────────────────────\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except ValueError as e:
            print(f"Invalid input: {e}\n")

# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI-powered IBC Space Function Mapper")
    parser.add_argument("--input", type=Path, default=TEST_CASES_PATH,
                        help="Input JSON file (default: test_cases.json)")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH,
                        help="Output JSON file (default: smart_mapper_results.json)")
    parser.add_argument("--single", action="store_true",
                        help="Run in interactive single-room mode")
    args = parser.parse_args()

    if args.single:
        run_interactive()
    else:
        run_batch(input_path=args.input, output_path=args.output)

if __name__ == "__main__":
    main()
