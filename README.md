# ContractGuard

**Catching construction billing leaks before payment goes out.**

Kaya AI × IIT India Hackathon 2026 — Track 3: Procurement

ContractGuard reconciles a construction project's full BOQ (Bill of
Quantities) and RA (Running Account) bill history automatically, catching
three kinds of billing leakage before payment is released:

- **Rate drift** — a line item billed at a rate that's drifted from the
  locked BOQ rate
- **Cumulative cross-bill double-billing** — a quantity re-billed across
  bills because a bill understates what was already certified
- **GST vs HSN mismatch** — GST charged at the wrong rate for a line
  item's HSN code

Every flag reports **WHERE → WHAT → RUPEE IMPACT → CONFIDENCE → CITATION**,
plus a one-click drafted vendor follow-up email disputing that line.

## Demo result

On our sample project — Shree Balaji Residency, Block B, contractor M/s
Verma Constructions, a 15-line-item BOQ checked against RA Bills 1–3 —
ContractGuard caught:

| Flag | Location | Issue | Rupee Impact |
|---|---|---|---|
| 1 | RA Bill 1, Steel reinforcement | GST charged 28% vs correct HSN rate 18% | ₹1,17,000 |
| 2 | RA Bill 3, Excavation | 250 m³ double-billed across bills | ₹53,100 |
| 3 | RA Bill 2, Brickwork | ₹995/m² charged vs BOQ rate ₹950/m² | ₹26,550 |
| | | **Total leakage caught** | **₹1,96,650** |

## Repo structure

```
contractguard/
├── data/
│   └── ContractGuard_Data_v0.json          # BOQ + RA Bill 1–3 sample data
├── reconciliation/
│   └── reconcile.py                        # detection engine (3 checks)
├── dashboard/
│   └── ContractGuard_Dashboard_Mockup_v4_STABLE.html   # dashboard mockup
└── docs/
    ├── ContractGuard_Sample_Documents.xlsx  # BOQ/RA bills + answer key
    └── slide-deck.pdf                       # slide deck
```

## Running the reconciliation engine

The detection logic is plain Python with no dependencies beyond the
standard library.

```bash
cd reconciliation
python3 reconcile.py ../data/ContractGuard_Data_v0.json
```

This prints every flag found (WHERE, WHAT, RUPEE IMPACT, CONFIDENCE,
CITATION), the total leakage caught, and a sample drafted vendor email for
the top flag.

## Viewing the dashboard

Open `dashboard/ContractGuard_Dashboard_Mockup_v4_STABLE.html` directly in
a browser — it's a self-contained file, no server or build step needed.
Click **Upload BOQ** → **Upload RA Bills** → **Analyze Contract** to walk
through the flow.

A hosted version is also available at: **[GitHub Pages link — add once
enabled]**

## How it works

1. Ingest a project's BOQ and full RA bill history.
2. Run three deterministic checks: rate drift, cumulative cross-bill
   check, and GST vs HSN.
3. Every flag reports WHERE → WHAT → RUPEE IMPACT → CONFIDENCE → CITATION.
4. One click drafts a ready-to-send vendor follow-up email.

## Team

- **Mohar Biswas** — Document Intelligence
- **Harshita Manav** — Mismatch Detection Logic + Deck
- **Dharmik Patel** — Interface, Agentic Layer & Demo
