# Saltmine · IBC Compliance Auditor 2.5.2

Saltmine is a premium, AI-powered compliance engine for International Building Code (IBC) audits. It replaces traditional keyword heuristics with **Gemini 2.0 Flash** to perform rigorous analysis of high-performance office designs.

---

## Key Features

- **Premium Identity**: A sleek, white and deep green design system built for high-end professional use.
- **Per-Floor Granular Audits**: Input square footage and occupancy for each floor independently to detect floor-specific violations.
- **IBC Chapters 7 & 8 Focus**: 16+ specialized checks for Fire Protection (Shafts, Smoke Barriers) and Interior Finishes (Flame Spread, Radiant Flux).
- **Intelligent Classification**: Chain-of-thought AI reasoning for complex space functions (e.g., "The Hive", "Boiler Room").

---

## Quick Start

### 1. Requirements
- Python 3.9+
- Gemini API Key

### 2. Installation
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Gemini API key in .env
echo "GEMINI_API_KEY=your_key_here" > .env
```

### 3. Launching the App
```bash
# Start Backend
python3 -m uvicorn api.main:app --port 8000 --reload

# Start Frontend
python3 -m http.server 3000 --directory frontend
```

Visit **[http://localhost:3000](http://localhost:3000)** to execute your first audit.

---

## File Structure

```
salt-mine/
├── api/
│   └── main.py          # FastAPI Backend (Audit Engine)
├── frontend/
│   └── index.html       # Ultra-premium React-based UI
├── ibcl_rules.json      # IBC Baseline Configuration
├── requirements.txt     # Backend Dependencies
└── README.md            # Platform Documentation
```

---

## Why Saltmine?

Traditional mappers fail on creative names and complex spatial densities. Saltmine evaluates **Name + Enclosure + Capacity + Area + Density** holistically, preventing:
- **False Passes** → Dangerous occupancy overloads.
- **False Fails** → Wasted space and unnecessary build costs.

---
© 2026 Saltmine IBC Compliance.
