"""
ContractGuard — Reconciliation Engine
======================================
Reads a project's BOQ + RA Bill history (ContractGuard_Data_v0.json schema)
and runs three deterministic checks:

  1. Rate drift        — rate_charged (RA bill) vs boq_rate (BOQ), same item_no
  2. Cumulative cross-bill check — stated cum_qty_prev vs the certified
                          cum_qty_todate from the actual previous bill
  3. GST vs HSN         — gst_pct_charged vs the correct rate for that hsn_code

Every flag reports: WHERE, WHAT, RUPEE IMPACT, CONFIDENCE, CITATION.

Usage:
    python3 reconcile.py ContractGuard_Data_v0.json
"""

import json
import sys


def load_data(path):
    with open(path, "r") as f:
        return json.load(f)


def index_boq(data):
    return {item["item_no"]: item for item in data["boq"]}


def fmt_inr(amount):
    """Format a number in Indian numbering style with a rupee sign."""
    n = round(amount)
    s = str(abs(n))
    if len(s) <= 3:
        grouped = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last3
    sign = "-" if n < 0 else ""
    return f"{sign}\u20b9{grouped}"


def check_rate_drift(data, boq_by_item):
    """Flag lines where rate_charged differs from the locked BOQ rate."""
    flags = []
    for bill in data["ra_bills"]:
        for line in bill["lines"]:
            boq_item = boq_by_item.get(line["item_no"])
            if not boq_item:
                continue
            boq_rate = boq_item["boq_rate"]
            rate_charged = line["rate_charged"]
            if round(rate_charged, 2) != round(boq_rate, 2):
                diff = rate_charged - boq_rate
                qty = line["qty_this_bill"]
                base_overcharge = diff * qty
                gst_pct = boq_item["gst_pct"]
                rupee_impact = base_overcharge * (1 + gst_pct / 100)
                flags.append({
                    "flag_type": "rate_drift",
                    "bill_no": bill["bill_no"],
                    "item_no": line["item_no"],
                    "description": boq_item["description"],
                    "where": f"RA Bill {bill['bill_no']}, Item {line['item_no']}",
                    "what": (
                        f"Billed at \u20b9{rate_charged}/{boq_item['unit']} vs the locked "
                        f"BOQ rate of \u20b9{boq_rate}/{boq_item['unit']}."
                    ),
                    "rupee_impact": rupee_impact,
                    "confidence": "HIGH",
                    "confidence_pct": 89,
                    "citation": (
                        f"BOQ item {line['item_no']}: rate {boq_rate} | "
                        f"RA Bill {bill['bill_no']}: rate_charged {rate_charged}"
                    ),
                })
    return flags


def check_cumulative_cross_bill(data, boq_by_item):
    """Flag lines whose stated 'previous cumulative' doesn't match what was
    actually certified in the true previous bill (i.e. double-billed qty)."""
    flags = []
    # certified[item_no] tracks the highest cum_qty_todate seen so far,
    # bill by bill, in chronological order.
    certified = {}
    bills_sorted = sorted(data["ra_bills"], key=lambda b: b["bill_no"])

    for bill in bills_sorted:
        for line in bill["lines"]:
            item_no = line["item_no"]
            stated_prev = line["cum_qty_prev"]
            actual_prev = certified.get(item_no, 0)

            if stated_prev < actual_prev:
                boq_item = boq_by_item.get(item_no)
                double_billed_qty = actual_prev - stated_prev
                rate = line["rate_charged"]
                gst_pct = line["gst_pct_charged"]
                base_overcharge = double_billed_qty * rate
                rupee_impact = base_overcharge * (1 + gst_pct / 100)
                flags.append({
                    "flag_type": "cumulative_mismatch",
                    "bill_no": bill["bill_no"],
                    "item_no": item_no,
                    "description": boq_item["description"] if boq_item else "",
                    "where": f"RA Bill {bill['bill_no']}, Item {item_no}",
                    "what": (
                        f"RA Bill {bill['bill_no']} states previous cumulative qty as "
                        f"{stated_prev}, but {actual_prev} was already certified — "
                        f"{double_billed_qty} re-billed."
                    ),
                    "rupee_impact": rupee_impact,
                    "confidence": "HIGH",
                    "confidence_pct": 91,
                    "citation": (
                        f"Certified cum_qty_todate (prior bill): {actual_prev} | "
                        f"RA Bill {bill['bill_no']} cum_qty_prev stated: {stated_prev}"
                    ),
                })

            # Update the certified record regardless, using this bill's own
            # reported cum_qty_todate.
            certified[item_no] = max(certified.get(item_no, 0), line["cum_qty_todate"])

    return flags


def check_gst_hsn(data, boq_by_item):
    """Flag lines where the GST % charged doesn't match the correct rate
    for that item's HSN code."""
    flags = []
    hsn_ref = data["hsn_reference"]
    for bill in data["ra_bills"]:
        for line in bill["lines"]:
            boq_item = boq_by_item.get(line["item_no"])
            if not boq_item:
                continue
            hsn_code = boq_item["hsn_code"]
            correct_gst = hsn_ref.get(hsn_code)
            charged_gst = line["gst_pct_charged"]
            if correct_gst is not None and charged_gst != correct_gst:
                taxable_value = line["qty_this_bill"] * line["rate_charged"]
                rupee_impact = taxable_value * (charged_gst - correct_gst) / 100
                flags.append({
                    "flag_type": "gst_mismatch",
                    "bill_no": bill["bill_no"],
                    "item_no": line["item_no"],
                    "description": boq_item["description"],
                    "where": f"RA Bill {bill['bill_no']}, Item {line['item_no']}",
                    "what": (
                        f"GST charged at {charged_gst}%, but HSN {hsn_code} is "
                        f"correctly rated at {correct_gst}%."
                    ),
                    "rupee_impact": rupee_impact,
                    "confidence": "HIGH",
                    "confidence_pct": 96,
                    "citation": (
                        f"HSN {hsn_code} \u2192 correct GST {correct_gst}% (BOQ) | "
                        f"charged {charged_gst}% (RA Bill {bill['bill_no']})"
                    ),
                })
    return flags


def draft_vendor_email(flag, contractor, project):
    subject = f"RA Bill {flag['bill_no']} — discrepancy on {flag['description']} (Item {flag['item_no']}) — {project}"
    body = (
        f"Dear {contractor},\n\n"
        f"During reconciliation of RA Bill {flag['bill_no']} for the {project} project, "
        f"we found a discrepancy on Item {flag['item_no']} ({flag['description']}):\n\n"
        f"{flag['what']}\n\n"
        f"Rupee impact: {fmt_inr(flag['rupee_impact'])}\n\n"
        f"Requested action: Please issue a credit note for the excess amount, or revise "
        f"the bill accordingly.\n\n"
        f"Kindly revert with a revised bill or credit note at your earliest convenience.\n\n"
        f"Regards,\nProject QS Team"
    )
    return subject, body


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "ContractGuard_Data_v0.json"
    data = load_data(path)
    boq_by_item = index_boq(data)

    flags = []
    flags += check_gst_hsn(data, boq_by_item)
    flags += check_cumulative_cross_bill(data, boq_by_item)
    flags += check_rate_drift(data, boq_by_item)

    flags.sort(key=lambda f: f["rupee_impact"], reverse=True)

    print(f"Project: {data['project']}")
    print(f"Contractor: {data['contractor']}")
    print(f"Bills reviewed: {len(data['ra_bills'])}")
    print(f"Flags raised: {len(flags)}")
    print("=" * 70)

    total = 0
    for i, f in enumerate(flags, 1):
        total += f["rupee_impact"]
        print(f"\nFLAG {i}: {f['flag_type'].upper()}")
        print(f"  WHERE      : {f['where']}")
        print(f"  WHAT       : {f['what']}")
        print(f"  RUPEE IMPACT: {fmt_inr(f['rupee_impact'])}")
        print(f"  CONFIDENCE : {f['confidence']} ({f['confidence_pct']}%)")
        print(f"  CITATION   : {f['citation']}")

    print("\n" + "=" * 70)
    print(f"TOTAL LEAKAGE CAUGHT: {fmt_inr(total)}")

    print("\n" + "=" * 70)
    print("SAMPLE DRAFTED VENDOR EMAIL (top flag):")
    subj, body = draft_vendor_email(flags[0], data["contractor"], data["project"])
    print(f"Subject: {subj}\n")
    print(body)


if __name__ == "__main__":
    main()
