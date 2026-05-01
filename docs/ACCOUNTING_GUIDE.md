# 💰 Accounting & Finance — How It Works
## دليل المحاسبة والمالية — نظام التخليص الجمركي KSA

---

## Overview

The **Accounting & Finance** menu (sequence 35 in the main navigation) covers the complete financial lifecycle of every customs clearance order — from the customer's portal request through ZATCA-compliant invoice submission and profit reporting.

It has **six sub-sections**:

| # | Sub-menu | Arabic | Purpose |
|---|----------|--------|---------|
| 1 | Customer Invoices | فواتير العملاء | Invoices issued TO the customer |
| 2 | Vendor Costs | تكاليف الشحنة | Costs paid BY you (duties, port, shipping) |
| 3 | ZATCA Integration | زاتكا | E-invoice compliance status |
| 4 | Bonds & Guarantees | الكفالات | Customs bonds lodged with authorities |
| 5 | Penalties & Appeals | الغرامات | Fines and appeal tracking |
| 6 | Financial Reports | التقارير المالية | Per-shipment P&L and cost analysis |

---

## The Full Accounting Cycle

```
Portal Request (customer submits)
        │
        ▼
   Officer Reviews
        │  [action_start_review]
        ▼
  Send Service Offer ──► Customer gets email with fee quote (Accept / Decline)
        │  [action_send_offer]        │
        │                            ▼
        │                   Customer Accepts ──► Service Invoice auto-created (Draft)
        ▼
  Approve ──► Clearance Order created (Draft state)
        │  [action_approve]
        │
        ▼  state: submitted → customs_review → inspection
        │
        ▼  state: duty_payment  ◄── AUTOMATIC TRIGGER
        │         └─► customs.shipment.cost record created (Customs Duty, confirmed)
        │         └─► Officer can click "Create Vendor Bill" → account.move (in_invoice)
        │
        ▼  state: released  ◄── AUTOMATIC TRIGGER
        │         └─► customs.service.invoice created + confirmed
        │         └─► ZATCA QR code generated (Phase 1 TLV)
        │         └─► ZATCA UBL 2.1 XML generated (Phase 2 ready)
        │         └─► account.move (out_invoice) posted in Odoo Accounting
        │
        ▼  state: delivered
              └─► Invoice sent to customer (email)
              └─► Officer submits to ZATCA portal [action_submit_to_zatca]
              └─► Payment tracked via SADAD reference
```

---

## Section 1 — Customer Invoices (فواتير العملاء)

**Model:** `customs.service.invoice`

### What it is
The invoice your company issues **to the importer/exporter** for the full cost of the clearance service. It is separate from what you pay to customs authorities or logistics providers.

### Invoice States

```
Draft ──► Confirmed ──► Sent to Client ──► Paid
                │
                └──► Cancelled (if not paid)
```

| State | Meaning |
|-------|---------|
| **Draft** | Auto-created when clearance is released, or when officer clicks "Create Service Invoice" |
| **Confirmed** | Invoice locked; ZATCA QR + XML generated; journal entry (out_invoice) posted automatically |
| **Sent to Client** | Email with invoice details sent to customer |
| **Paid** | Full payment recorded; amount_due = 0 |
| **Cancelled** | Voided (cannot cancel a paid invoice) |

### What Gets Billed

The invoice is auto-populated from the clearance order fields:

| Line Type | Source Field | VAT |
|-----------|-------------|-----|
| Service Fee | `clearance.service_fee` | 15% |
| Port Charges | `clearance.port_charges` | 15% |
| Demurrage | `clearance.demurrage_fee` | 15% |
| Other Charges | `clearance.other_charges` | 15% |
| Customs Duty Pass-Through | `clearance.total_duty_amount` | **0%** (exempt) |

> **Saudi VAT Rule:** Customs duties are a pass-through cost — they are collected on behalf of the government and are **not subject to service VAT**. Only your service fees carry the 15% VAT.

### Buttons on the Invoice Form

| Button | When Visible | What It Does |
|--------|-------------|--------------|
| **Confirm** | Draft | Locks invoice; generates ZATCA QR + XML; posts journal entry |
| **Send to Client** | Confirmed | Sends branded email invoice to partner |
| **Post to Accounting** | Confirmed / Sent | Creates `account.move` (out_invoice) if not already posted |
| **Mark as Paid** | Confirmed / Sent | Records full payment; sets state to Paid |
| **Submit to ZATCA ▶** | Confirmed / Sent | Marks as cleared; assigns ZATCA submission ID |
| **Cancel** | Draft / Confirmed / Sent | Voids the invoice |
| **Reset to Draft** | Cancelled | Returns to draft for correction |

### Journal Entry (DR/CR)

When the invoice is confirmed, Odoo automatically posts:

```
DR  Accounts Receivable (partner)         SAR [total incl. VAT]
    CR  Customs Clearance Revenue         SAR [subtotal excl. VAT]
    CR  VAT Output — Tax Payable (15%)    SAR [vat_amount]
```

### Sub-menus

- **All Invoices** — full list of all service invoices across all clearances
- **Unpaid** — filtered to invoices in `draft / confirmed / sent` state with `amount_due > 0`

---

## Section 2 — Vendor Costs (تكاليف الشحنة)

**Model:** `customs.shipment.cost`

### What it is
Every cost your company **pays out** to third parties: customs duties, port authorities, shipping lines, transporters, inspectors. These are your **expense / cost-of-sales** entries.

### Cost Types

| Type | Arabic | Common Use |
|------|--------|-----------|
| `customs_duty` | رسوم جمركية | Duties assessed by ZATCA/Customs Authority |
| `shipping` | رسوم شحن | Shipping line fees |
| `clearance_fee` | رسوم تخليص | Third-party broker sub-fees |
| `transport` | نقل | Land/air transport |
| `port_charges` | رسوم ميناء | Port handling |
| `demurrage` | غرامة تأخير | Container overstay penalty |
| `inspection` | رسوم فحص | Physical inspection charges |
| `vat_import` | ضريبة استيراد | Import VAT (reverse charge) |
| `storage` | تخزين | Warehouse fees |
| `insurance` | تأمين | Cargo insurance |

### Cost States

```
Draft ──► Confirmed ──► Billed (Vendor Bill created) ──► Paid
```

### Automatic Trigger: `duty_payment` state

When a clearance order reaches the **`duty_payment`** state, the system automatically:
1. Creates a `customs.shipment.cost` record with `cost_type = customs_duty`
2. Sets the amount from `clearance.total_duty_amount`
3. Marks it as `VAT Exempt = True` (duties not subject to VAT on cost side)
4. Confirms it immediately

The officer then clicks **"Create Vendor Bill"** to generate an `account.move` (in_invoice) in Odoo Accounting.

### Vendor Bill Journal Entry

```
DR  Customs Duty Expense Account          SAR [amount]
    CR  Accounts Payable (vendor)         SAR [amount]
```

### Profit Calculation

The system computes per-clearance P&L from these two sides:

```
Total Revenue  = SUM(service_invoice.total) where state in (confirmed, sent, paid)
Total Cost     = SUM(shipment_cost.total_amount) where state in (confirmed, billed, paid)
               + legacy fields (total_duty_amount + port_charges + demurrage_fee)
                 IF no cost lines exist

Net Profit     = Total Revenue − Total Cost
Profit Margin  = (Net Profit / Total Revenue) × 100
```

These fields appear on every clearance order and feed the **Financial Reports**.

### Sub-menus

- **All Costs** — every cost line across all clearances
- **Unpaid Costs** — cost lines in `draft / confirmed` state (not yet billed/paid)

---

## Section 3 — ZATCA Integration (زاتكا)

**Model:** `customs.service.invoice` (filtered by `zatca_status`)

### What it is
Saudi Arabia's ZATCA (Zakat, Tax and Customs Authority) requires all B2B invoices to be submitted electronically. The system handles both phases:

| Phase | What | Status |
|-------|------|--------|
| **Phase 1** | QR code (TLV Base64) embedded in invoice | ✅ Auto-generated on confirm |
| **Phase 2** | UBL 2.1 XML submitted to ZATCA portal | ✅ XML generated; mock submission |

### ZATCA Invoice Status Values

| Status | Arabic | Meaning |
|--------|--------|---------|
| `pending` | بانتظار الإرسال | Not yet submitted |
| `submitted` | مرسل | Sent to ZATCA, awaiting response |
| `cleared` | معتمد | ZATCA approved and cleared |
| `error` | خطأ | Submission rejected; needs correction |

### TLV QR Code Structure (Phase 1)

The QR code contains 5 TLV (Tag-Length-Value) fields:

| Tag | Field |
|-----|-------|
| 1 | Seller name (company) |
| 2 | Seller VAT number |
| 3 | Invoice date/time (ISO 8601) |
| 4 | Total amount incl. VAT |
| 5 | VAT amount |

### Sub-menus

- **ZATCA Invoice Status** — all service invoices with their ZATCA status
- **Pending ZATCA** — invoices with `zatca_status in (pending, submitted)`
- **ZATCA Cleared** — invoices confirmed cleared by ZATCA

### Workflow

```
Invoice Confirmed
      │
      ├─► QR Code (Base64 TLV) auto-generated ──► stored in fatoorah_qr_code
      ├─► UBL 2.1 XML auto-generated ──► stored in zatca_xml
      │
      ▼
Officer clicks "Submit to ZATCA ▶"
      │
      ├─► zatca_status → 'cleared'
      ├─► zatca_submission_id assigned
      └─► fatoorah_invoice_no set (ZATCA-{invoice_no})
```

> **Production note:** Replace the mock submission in `action_submit_to_zatca()` with the actual ZATCA API endpoint and authentication headers when going live.

---

## Section 4 — Bonds & Guarantees (الكفالات)

**Model:** `customs.bond`

### What it is
Customs bonds (كفالات) are financial guarantees lodged with Saudi Customs or the Ministry of Finance to cover:
- Temporary admission (إدخال مؤقت) of goods
- Suspended duty (إيقاف رسوم) for goods in transit or re-export
- ATA Carnet guarantees

### Bond States

```
Draft ──► Active ──► Released
                └──► Forfeited (if customs claims the bond)
```

| State | Meaning |
|-------|---------|
| `draft` | Bond created, not yet lodged |
| `active` | Bond lodged with customs authority |
| `released` | Goods cleared; bond returned / cancelled |
| `forfeited` | Bond called by customs (penalty situation) |

### Expiry Alerts
The `is_expired` flag is computed: if the bond has an expiry date and today's date exceeds it, `is_expired = True`. The list view highlights expired bonds in red.

---

## Section 5 — Penalties & Appeals (الغرامات)

**Model:** `customs.penalty`

### What it is
Fines issued by Saudi Customs (ZATCA) or port authorities against a clearance order. Tracks the appeal process.

### Penalty States

```
Draft ──► Issued ──► Appealing ──► Settled
                              └──► Waived
```

| State | Meaning |
|-------|---------|
| `draft` | Penalty received, not yet confirmed |
| `issued` | Official penalty from authority |
| `appealing` | Formal appeal submitted |
| `settled` | Paid or resolved |
| `waived` | Authority waived the penalty |

### Penalty Types

- `late_declaration` — Late ACD submission
- `documentation` — Missing/incorrect documents
- `valuation` — Incorrect declared goods value
- `classification` — Wrong HS code
- `prohibited` — Restricted goods violation
- `other` — Miscellaneous

---

## Section 6 — Financial Reports (التقارير المالية)

### Profit per Shipment (ربح الشحنة)

**Action:** `action_customs_clearance_profit`
**Views:** List → Pivot → Graph

Shows the computed financial fields on every clearance order:

| Column | Formula |
|--------|---------|
| Total Revenue | Sum of confirmed service invoices |
| Total Cost | Sum of confirmed cost lines + legacy duty/port/demurrage |
| Net Profit | Revenue − Cost |
| Profit Margin % | (Profit / Revenue) × 100 |

Use the **Pivot** view to group by clearance type, port, or month. Use the **Graph** view for trend analysis.

### Cost Analysis (تحليل التكاليف)

**Action:** `action_customs_shipment_cost`

Opens the full cost lines list. Group by:
- `cost_type` — see which cost category dominates
- `clearance_id` — per-shipment breakdown
- `vendor_id` — supplier spend analysis

---

## End-to-End Example: Import Shipment

```
1. PORTAL — Customer submits import request
   └─► PRT/2026/00001 created (state: draft)

2. OFFICER — Starts review, sets estimated_service_fee = 2,500 SAR
             estimated_duty_amount = 15,000 SAR
   └─► Clicks "Send Service Offer"
   └─► Customer receives email: Fee SAR 2,500 + VAT 375 + Duty 15,000 = SAR 17,875 total

3. CUSTOMER — Clicks "Accept Offer" in email
   └─► offer_state → accepted
   └─► Draft service invoice auto-created on linked clearance

4. OFFICER — Clicks "Approve & Create Order"
   └─► customs.clearance created (CLR/2026/00042, state: draft)
   └─► Approval email sent to customer

5. CLEARANCE WORKFLOW:
   draft → submitted → customs_review → inspection

6. STATE: duty_payment  ◄── AUTOMATIC
   └─► customs.shipment.cost: "Customs Duty — CLR/2026/00042" = 15,000 SAR (confirmed)
   └─► Officer clicks "Create Vendor Bill" → account.move in_invoice posted

7. STATE: released  ◄── AUTOMATIC
   └─► customs.service.invoice SVC/2026/00018 created + confirmed
       Lines:
         - Clearance Service — CLR/2026/00042    2,500.00 SAR  (+15% VAT = 375.00)
         - Customs Duties (FASAH ref: FASAH-XXX) 15,000.00 SAR (VAT exempt)
       Total: 17,875.00 SAR
   └─► Journal entry posted (DR Receivable / CR Revenue + VAT Output)
   └─► ZATCA QR code generated
   └─► ZATCA XML generated

8. OFFICER — Clicks "Send to Client"
   └─► Invoice email sent to customer

9. OFFICER — Clicks "Submit to ZATCA ▶"
   └─► zatca_status → cleared
   └─► Submission ID recorded

10. CUSTOMER — Pays via SADAD or bank transfer
    └─► Officer clicks "Mark as Paid"
    └─► state → paid, amount_due = 0

11. REPORTS:
    Revenue: 17,875 SAR | Cost: 15,000 SAR | Profit: 2,875 SAR | Margin: 16.1%
```

---

## Key Models Reference

| Model | Table | Description |
|-------|-------|-------------|
| `customs.service.invoice` | `customs_service_invoice` | Customer-facing tax invoice |
| `customs.service.invoice.line` | `customs_service_invoice_line` | Invoice line items |
| `customs.shipment.cost` | `customs_shipment_cost` | Vendor costs / expenses |
| `customs.bond` | `customs_bond` | Customs bonds & guarantees |
| `customs.penalty` | `customs_penalty` | Fines & appeals |
| `customs.clearance` | `customs_clearance` | Main clearance order (extended with financials) |

---

## Sequences

| Sequence Code | Format | Example |
|--------------|--------|---------|
| `customs.service.invoice` | `SVC/{year}/{5-digits}` | `SVC/2026/00018` |
| `customs.bond` | `BOND/{year}/{5-digits}` | `BOND/2026/00003` |
| `customs.penalty` | `PEN/{year}/{5-digits}` | `PEN/2026/00001` |

---

## Access Rights

| Group | Customer Invoices | Vendor Costs | ZATCA | Bonds | Penalties |
|-------|:-:|:-:|:-:|:-:|:-:|
| `group_customs_user` | Read/Write | Read/Write | Read | Read/Write | Read |
| `group_customs_manager` | Full | Full | Full | Full | Full |

---

*Generated for Customs Clearance KSA v2 — Odoo 17.0 | ZATCA · FASAH · SABER Compliant*
