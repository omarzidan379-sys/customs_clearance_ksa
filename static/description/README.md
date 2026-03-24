# Customs Clearance Module for Odoo 17
## نظام التخليص الجمركي

### Version 1.0.0

---

## Overview

A comprehensive customs clearance management system for Odoo 17, supporting full import/export operations for Egyptian and regional customs workflows.

---

## Features

### Core Clearance Management
- **Clearance Orders** with full lifecycle workflow (Draft → Submitted → Customs Review → Inspection → Duty Payment → Released → Delivered)
- Support for **Import, Export, Transit, and Temporary Admission**
- Multi-company support
- Priority flagging (Normal / Urgent / Very Urgent)

### Shipment Tracking
- Shipment records linked to clearance orders
- **Container management** (20GP, 40GP, 40HC, Reefer, LCL, etc.)
- Vessel, voyage, Bill of Lading tracking
- ETA and actual arrival tracking

### HS Code Management
- Full HS Code library with EN and Arabic descriptions
- Automatic chapter/heading extraction
- Default import/export duty rates per HS code
- VAT rates per commodity

### Customs Broker Management
- Broker profiles with license numbers and expiry tracking
- Authorized customs offices per broker
- Service fee configuration (fixed or percentage)
- Clearance history per broker

### Ports & Customs Offices
- Seaports, Airports, Land Borders, Customs Offices, Dry Ports
- UN/LOCODE support

### Document Management
- Pre-configured document types: Bill of Lading, Commercial Invoice, Packing List, Certificate of Origin, Customs Declaration, Insurance Certificate, Health Certificate, Import License, Form 4
- Document status tracking (Pending → Received → Verified / Rejected)
- File attachments per document

### Duties & Taxes Calculation
- Configurable duty types: Customs Duty, VAT, Excise Tax, Port Fees, Inspection Fees
- Percentage-based or fixed amount duties
- Automatic calculation from CIF value
- Payment reference tracking

### Financial Integration
- CIF value calculation (Goods + Freight + Insurance)
- Total cost summary
- One-click **Vendor Bill creation** for broker fees and duties
- Multi-currency support

### Reports
- **PDF Customs Clearance Report** with full goods lines, duties table, document checklist, and signature blocks
- Bilingual (English/Arabic) labels

---

## Installation

1. Copy the `customs_clearance` folder to your Odoo addons directory
2. Restart Odoo server
3. Go to **Apps** → Search "Customs Clearance" → Install

---

## Module Structure

```
customs_clearance/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── customs_clearance.py      # Main clearance order + goods lines
│   ├── customs_shipment.py       # Shipments + containers
│   ├── customs_hs_code.py        # HS code library
│   ├── customs_port.py           # Ports & customs offices
│   ├── customs_broker.py         # Customs brokers
│   ├── customs_document.py       # Document types + documents
│   └── customs_duty.py           # Duty types + duty lines
├── views/
│   ├── customs_clearance_views.xml
│   ├── customs_shipment_views.xml
│   ├── customs_hs_code_views.xml
│   ├── customs_port_views.xml
│   ├── customs_broker_views.xml
│   ├── customs_document_views.xml
│   ├── customs_duty_views.xml
│   └── customs_menu_views.xml
├── security/
│   ├── customs_clearance_security.xml
│   └── ir.model.access.csv
├── data/
│   ├── customs_sequence_data.xml
│   └── customs_document_type_data.xml
├── report/
│   ├── customs_clearance_report.xml
│   └── customs_clearance_report_template.xml
└── static/description/
    └── index.html
```

---

## User Groups

| Group | Permissions |
|-------|------------|
| Customs User | Read, Write, Create (no delete) |
| Customs Manager | Full access including configuration |

---

## Sequence Prefixes

| Type | Prefix | Example |
|------|--------|---------|
| Import | IMP/YYYY/ | IMP/2025/00001 |
| Export | EXP/YYYY/ | EXP/2025/00001 |
| Transit | TRN/YYYY/ | TRN/2025/00001 |
| Temporary | TMP/YYYY/ | TMP/2025/00001 |

---

## Roadmap (v2.0)

- [ ] Integration with Egyptian Customs Authority (NAFEZA / ACI)
- [ ] WhatsApp/SMS notifications for status changes
- [ ] Customs tariff import wizard (bulk HS code upload)
- [ ] Dashboard with KPIs and analytics
- [ ] Landed cost automatic posting to stock valuation
- [ ] Mobile-friendly clearance checklist

---

## Author

Developed as a professional Odoo 17 module for customs clearance operations.

**License:** LGPL-3
