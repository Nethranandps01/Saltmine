# Salt-Mine · IBC Space Function Mapper POC

AI-powered replacement for the brittle keyword-based `spaceFunctionMapper.js`.
Uses **Gemini 2.0 Flash** with chain-of-thought reasoning to classify real estate
block instances into [IBC occupancy categories](https://codes.iccsafe.org/content/IBC2021P1).

---

## Quick Start

```bash
# 1. Install dependency
pip install google-generativeai

# 2. Set your Gemini API key
export GEMINI_API_KEY="your-key-here"

# 3. Run the legacy heuristic mapper (baseline)
python legacy_mapper.py

# 4. Run the AI mapper
python smart_mapper.py

# 5. Generate comparison report
python compare_mappers.py
open report.html
```

---

## File Structure

```
salt-mine/
├── ibc_rules.json              # IBC config: 8 categories, load factors, hints
├── test_cases.json             # 25 test cases with ground truth labels
├── smart_mapper.py             # 🤖 AI mapper (Gemini 2.0 Flash, chain-of-thought)
├── legacy_mapper.py            # 📜 Legacy heuristic mapper (keyword matching)
├── compare_mappers.py          # 📊 Comparison engine + HTML report generator
├── smart_mapper_results.json   # [generated] AI mapper output
├── legacy_mapper_results.json  # [generated] Legacy mapper output
└── report.html                 # [generated] Visual comparison report
```

---

## The 8 IBC Occupancy Categories

| Category | Load Factor | Method | Typical Use |
|---|---|---|---|
| Business Areas | 150 | Gross | Open-plan desks, cubicles |
| Concentrated Business | 50 | Gross | Call centers, trading floors |
| Assembly – Unconcentrated | 15 | Net | Meeting rooms with tables |
| Assembly – Concentrated | 7 | Net | Auditoriums, town halls |
| Storage | 300 | Gross | IT closets, utility rooms |
| Mercantile | 60 | Gross | Showrooms, sales floors |
| Kitchens | 200 | Gross | Commercial food prep only |
| Classroom | 20 | Net | Education/instruction spaces |

---

## Interactive Mode

Classify a single room from the command line:

```bash
python smart_mapper.py --single
```

---

## Why This Matters

The legacy mapper fails on creative room names like "Mars", "The Hive", "Boiler Room".
A wrong IBC mapping leads to:
- **False Pass** → dangerous occupancy overload  
- **False Fail** → wasted space and unnecessary cost

The AI mapper evaluates **Name + Enclosure + Capacity + Area + Density together**,
achieving significantly higher accuracy on the hard (creative name) test cases.
