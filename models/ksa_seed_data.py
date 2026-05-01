#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  Customs Clearance — Demo Data Seed Script
  Module: customs_clearance  |  Odoo 17  |  Version 2.0
================================================================================

  PURPOSE:
    Populate ALL models in the customs_clearance module with realistic
    Saudi Arabia demo data so you can demonstrate every feature to the client
    immediately after installation.

  WHAT IT CREATES:
    - 3  Customs Brokers (with ZATCA codes + FASAH usernames)
    - 4  HS Codes (with Saudi duty rates + regulatory flags)
    - 5  Clearance Orders across different states and lanes
         (2 import Green Lane, 1 import Red Lane, 1 export, 1 transit)
    - Goods Lines, Duty Lines, and Documents per clearance order
    - 2  Shipments with containers linked to clearance orders

  HOW TO RUN:
    Option A — Odoo Shell (recommended):
      $ cd /path/to/odoo
      $ python odoo-bin shell -d <your_database> -c odoo.conf
      # >>> exec(open(/path/to/ksa_seed_data.py).read())

    Option B — Direct shell command:
      $ python odoo-bin shell -d <your_database> --no-http \
            < /path/to/ksa_seed_data.py

    Option C — From within Odoo (Developer mode):
      Settings → Technical → Shell → paste and execute

  REQUIREMENTS:
    - customs_clearance module must be installed
    - At least one company configured in Odoo
    - Run as Administrator user

================================================================================
"""

import logging
from datetime import date, timedelta

_logger = logging.getLogger(__name__)

print("=" * 70)
print("  Customs Clearance KSA — Demo Data Seed Script")
print("  Starting data creation...")
print("=" * 70)

env = env  # noqa: F821 — available in Odoo shell context

# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_or_create_partner(name, vat=None, country_code='SA', city=None):
    Partner = env['res.partner']
    p = Partner.search([('name', '=', name)], limit=1)
    if not p:
        country = env['res.country'].search([('code', '=', country_code)], limit=1)
        vals = {'name': name, 'company_type': 'company', 'country_id': country.id if country else False}
        if vat:
            vals['vat'] = vat
        if city:
            vals['city'] = city
        p = Partner.create(vals)
        print(f"  ✓ Created partner: {name}")
    return p


def get_currency(code='SAR'):
    return env['res.currency'].search([('name', '=', code)], limit=1)


def get_country(code):
    return env['res.country'].search([('code', '=', code)], limit=1)


def get_port(xml_id_suffix):
    try:
        return env.ref(f'customs_clearance.{xml_id_suffix}')
    except Exception:
        # Fallback: search by name fragment
        return env['customs.port'].search([], limit=1)


SAR = get_currency('SAR')
SA  = get_country('SA')
CN  = get_country('CN')
DE  = get_country('DE')
AE  = get_country('AE')
US  = get_country('US')


# ════════════════════════════════════════════════════════════════════════════
# 1. PARTNERS (Importers / Exporters)
# ════════════════════════════════════════════════════════════════════════════
print("\n[1/7] Creating partners...")

partner_almarai     = get_or_create_partner('Al Marai Company / شركة المراعي',    vat='3000000001', city='Riyadh')
partner_sabic       = get_or_create_partner('SABIC — Saudi Basic Industries',      vat='3000000002', city='Riyadh')
partner_tamimi      = get_or_create_partner('Tamimi Markets / أسواق التميمي',      vat='3000000003', city='Dammam')
partner_siemens     = get_or_create_partner('Siemens Saudi Arabia',                vat='3000000004', city='Jeddah')
partner_alibaba     = get_or_create_partner('Alibaba Trading LLC',                 country_code='CN', city='Shenzhen')

# Broker partners
broker_partner_1 = get_or_create_partner('Abdullah Al-Rashidi Customs Clearance / مكتب عبدالله الراشدي للتخليص', city='Jeddah')
broker_partner_2 = get_or_create_partner('Gulf Clearance Services / خدمات الخليج للتخليص',                       city='Dammam')
broker_partner_3 = get_or_create_partner('Royal Star Customs Brokers / وسطاء الجمارك النجم الملكي',              city='Riyadh')

print("  ✓ Partners ready")


# ════════════════════════════════════════════════════════════════════════════
# 2. CUSTOMS BROKERS
# ════════════════════════════════════════════════════════════════════════════
print("\n[2/7] Creating customs brokers...")

Broker = env['customs.broker']

def make_broker(name, partner, license_no, zatca_code, fasah_user, expiry_days, is_aeo=False):
    b = Broker.search([('license_number', '=', license_no)], limit=1)
    if not b:
        b = Broker.create({
            'name':              name,
            'partner_id':        partner.id,
            'license_number':    license_no,
            'license_expiry_date': (date.today() + timedelta(days=expiry_days)).isoformat(),
            'zatca_broker_code': zatca_code,
            'fasah_username':    fasah_user,
            'specialization':    'both',
            'service_fee_type':  'percentage',
            'service_fee':       1.5,
            'is_aeo_broker':     is_aeo,
            'aeo_cert_no':       f'AEO-{zatca_code}-2025' if is_aeo else False,
        })
        print(f"  ✓ Broker: {name}")
    return b

broker_1 = make_broker('Abdullah Al-Rashidi Customs Clearance', broker_partner_1, 'KSA-BRK-10234', 'ZATCA-BR-1234', 'alrashidi_fasah', 365, is_aeo=True)
broker_2 = make_broker('Gulf Clearance Services',               broker_partner_2, 'KSA-BRK-20891', 'ZATCA-BR-2089', 'gulf_clr_fasah',  180)
broker_3 = make_broker('Royal Star Customs Brokers',            broker_partner_3, 'KSA-BRK-30456', 'ZATCA-BR-3045', 'royalstar_fasah', 730)


# ════════════════════════════════════════════════════════════════════════════
# 3. HS CODES (Saudi-specific rates + regulatory flags)
# ════════════════════════════════════════════════════════════════════════════
print("\n[3/7] Creating HS codes...")

HSCode = env['customs.hs.code']

hs_data = [
    {
        'code': '8471.30',
        'name': 'Laptop Computers / Portable ADP machines',
        'name_ar': 'أجهزة الحاسوب المحمولة',
        'import_duty_rate': 5.0, 'vat_rate': 15.0, 'excise_rate': 0.0, 'gcc_duty_rate': 0.0,
        'requires_saber': True, 'requires_citc': True, 'requires_sfda': False,
        'category': 'Electronics',
    },
    {
        'code': '0201.10',
        'name': 'Beef / Carcasses and half-carcasses, fresh or chilled',
        'name_ar': 'لحم البقر الطازج أو المبرد',
        'import_duty_rate': 5.0, 'vat_rate': 0.0, 'excise_rate': 0.0, 'gcc_duty_rate': 0.0,
        'requires_saber': False, 'requires_citc': False, 'requires_sfda': True,
        'category': 'Food',
    },
    {
        'code': '2402.20',
        'name': 'Cigarettes containing tobacco',
        'name_ar': 'سجائر تحتوي على التبغ',
        'import_duty_rate': 100.0, 'vat_rate': 15.0, 'excise_rate': 100.0, 'gcc_duty_rate': 100.0,
        'requires_saber': False, 'requires_citc': False, 'requires_sfda': False,
        'is_restricted': True, 'category': 'Tobacco',
    },
    {
        'code': '8517.12',
        'name': 'Mobile phones / Telephones for cellular networks',
        'name_ar': 'الهواتف المحمولة والأجهزة اللاسلكية',
        'import_duty_rate': 5.0, 'vat_rate': 15.0, 'excise_rate': 0.0, 'gcc_duty_rate': 0.0,
        'requires_saber': True, 'requires_citc': True, 'requires_sfda': False,
        'category': 'Telecom',
    },
    {
        'code': '3004.50',
        'name': 'Medicaments containing vitamins — retail packs',
        'name_ar': 'أدوية تحتوي على فيتامينات — عبوات للتجزئة',
        'import_duty_rate': 0.0, 'vat_rate': 0.0, 'excise_rate': 0.0, 'gcc_duty_rate': 0.0,
        'requires_saber': False, 'requires_citc': False, 'requires_sfda': True,
        'category': 'Pharmaceuticals',
    },
    {
        'code': '8703.23',
        'name': 'Motor cars — cylinder capacity 1000–1500cc',
        'name_ar': 'سيارات ركاب محرك 1000–1500 سم مكعب',
        'import_duty_rate': 12.0, 'vat_rate': 15.0, 'excise_rate': 0.0, 'gcc_duty_rate': 5.0,
        'requires_saber': True, 'requires_citc': False, 'requires_sfda': False,
        'category': 'Automotive',
    },
]

hs_map = {}
for h in hs_data:
    existing = HSCode.search([('code', '=', h['code'])], limit=1)
    if not existing:
        existing = HSCode.create(h)
        print(f"  ✓ HS Code {h['code']}: {h['name'][:40]}")
    hs_map[h['code']] = existing

print("  ✓ HS Codes ready")


# ════════════════════════════════════════════════════════════════════════════
# 4. DUTY TYPES (lookup pre-loaded seed data)
# ════════════════════════════════════════════════════════════════════════════
print("\n[4/7] Loading duty types...")

DutyType = env['customs.duty.type']

def get_duty(code):
    d = DutyType.search([('code', '=', code)], limit=1)
    if not d:
        d = DutyType.search([], limit=1)  # fallback
    return d

dt_customs_5  = get_duty('KSA-CD-5')
dt_customs_12 = get_duty('KSA-CD-12')
dt_vat_15     = get_duty('KSA-VAT-15')
dt_excise_tob = get_duty('KSA-EX-TOB')
dt_port_fee   = get_duty('KSA-PSF')
dt_gcc_zero   = get_duty('KSA-GCC-0')

print("  ✓ Duty types loaded")


# ════════════════════════════════════════════════════════════════════════════
# 5. DOCUMENT TYPES (lookup pre-loaded seed data)
# ════════════════════════════════════════════════════════════════════════════
print("\n[5/7] Loading document types...")

DocType = env['customs.document.type']

def get_doctype(code):
    return DocType.search([('code', '=', code)], limit=1)

dt_bl         = get_doctype('BL')
dt_inv        = get_doctype('INV')
dt_pl         = get_doctype('PL')
dt_coo        = get_doctype('COO')
dt_fasah      = get_doctype('FASAH-DEC')
dt_acd        = get_doctype('ACD')
dt_saber_scoc = get_doctype('SABER-SCOC')
dt_sfda       = get_doctype('SFDA')
dt_citc       = get_doctype('CITC')
dt_release    = get_doctype('RELEASE')
dt_sadad      = get_doctype('SADAD')

print("  ✓ Document types loaded")


# ════════════════════════════════════════════════════════════════════════════
# 6. SHIPMENTS
# ════════════════════════════════════════════════════════════════════════════
print("\n[6/7] Creating shipments...")

Shipment = env['customs.shipment']

def make_shipment(name, stype, vessel, voyage, bl, origin_code, dest_code, eta_days, state='arrived'):
    s = Shipment.search([('name', '=', name)], limit=1)
    if not s:
        port_origin = env['customs.port'].search([('code', '=', origin_code)], limit=1)
        port_dest   = env['customs.port'].search([('code', '=', dest_code)],   limit=1)
        s = Shipment.create({
            'name':               name,
            'shipment_type':      stype,
            'vessel_name':        vessel,
            'voyage_number':      voyage,
            'bill_of_lading_no':  bl,
            'port_origin_id':     port_origin.id if port_origin else False,
            'port_destination_id':port_dest.id   if port_dest   else False,
            'departure_date':     (date.today() - timedelta(days=12)).isoformat(),
            'eta':                (date.today() - timedelta(days=2)).isoformat(),
            'actual_arrival_date':(date.today() - timedelta(days=1)).isoformat(),
            'shipper_id':         partner_alibaba.id,
            'consignee_id':       partner_almarai.id,
            'gross_weight':       18500.0,
            'volume':             42.5,
            'packages_count':     320,
            'state':              state,
        })
        # Add a container
        env['customs.container'].create({
            'shipment_id':      s.id,
            'container_number': f'MSCU{name[-4:]}1234',
            'container_type':   '40hc',
            'seal_number':      f'SEAL{name[-4:]}001',
            'gross_weight':     18500.0,
            'volume':           67.7,
        })
        print(f"  ✓ Shipment: {name}")
    return s

shipment_1 = make_shipment('SHP/2026/0001', 'sea', 'MSC DIANA',     'MD-1142W', 'MSCUJD2600001', 'CNSHA', 'SAJED',  -1)
shipment_2 = make_shipment('SHP/2026/0002', 'air', 'Saudia Cargo',  'SV-4421',  'AWB-176-22341', 'DEDUS', 'SARUH',  -1)


# ════════════════════════════════════════════════════════════════════════════
# 7. CLEARANCE ORDERS
# ════════════════════════════════════════════════════════════════════════════
print("\n[7/7] Creating clearance orders...")

Clearance = env['customs.clearance']
port_jeddah  = env['customs.port'].search([('code', '=', 'SAJED')],    limit=1)
port_dammam  = env['customs.port'].search([('code', '=', 'SADMM')],    limit=1)
port_riyadh  = env['customs.port'].search([('code', '=', 'SARUH')],    limit=1)
czat_jeddah  = env['customs.port'].search([('code', '=', 'CZATJED')],  limit=1)
czat_riyadh  = env['customs.port'].search([('code', '=', 'CZATRUH')],  limit=1)


# ────────────────────────────────────────────────────────────────────────────
# ORDER 1: Import — Green Lane — RELEASED (laptops from China)
# ────────────────────────────────────────────────────────────────────────────
def create_clearance_1():
    existing = Clearance.search([('fasah_declaration_no', '=', 'FASAH-2026-JED-00123')], limit=1)
    if existing:
        print("  - Order 1 already exists, skipping")
        return existing

    cl = Clearance.create({
        'clearance_type':      'import',
        'partner_id':          partner_almarai.id,
        'broker_id':           broker_1.id,
        'port_id':             port_jeddah.id,
        'customs_office_id':   czat_jeddah.id,
        'country_origin_id':   CN.id,
        'date':                (date.today() - timedelta(days=5)).isoformat(),
        'expected_clearance_date': (date.today() - timedelta(days=1)).isoformat(),
        'actual_clearance_date':   (date.today() - timedelta(days=1)).isoformat(),
        'shipment_id':         shipment_1.id,

        # Saudi references
        'fasah_declaration_no': 'FASAH-2026-JED-00123',
        'acd_reference_no':     'ACD-2026-00445',
        'acd_submission_date':  (date.today() - timedelta(days=7)).isoformat(),
        'fatoorah_invoice_no':  'FAT-INV-2026-8821',
        'bill_of_lading_no':    'MSCUJD2600001',
        'customs_declaration_no': 'BYN-2026-JED-9001',
        'sadad_payment_ref':    'SADAD-2026-PAY-33412',
        'release_permit_no':    'RELEASE-JED-2026-4521',
        'masar_tracking_no':    'MASAR-JED-2026-7712',
        'release_date':         (date.today() - timedelta(days=1)).isoformat(),

        # SABER
        'requires_saber':      True,
        'saber_pcoc_no':       'SABER-PCOC-47821',
        'saber_scoc_no':       'SABER-SCOC-99134',
        'saber_scoc_expiry':   (date.today() + timedelta(days=90)).isoformat(),
        'saber_scoc_verified': True,

        # Regulatory
        'requires_citc':       True,
        'citc_certificate_no': 'CITC-2026-LAP-0012',
        'citc_approved':       True,

        # AEO
        'is_aeo':              True,
        'aeo_certificate_no':  'AEO-KSA-2025-0089',

        # Financial
        'currency_id':         SAR.id,
        'goods_value':         185000.0,
        'freight_amount':       8500.0,
        'insurance_amount':     2200.0,
        'service_fee':          3900.0,
        'port_charges':         1200.0,

        # Lane & compliance
        'inspection_lane':     'green',
        'payment_status':      'paid',
        'state':               'released',
    })

    # Goods lines
    env['customs.clearance.line'].create([
        {
            'clearance_id': cl.id, 'sequence': 10,
            'description': 'Laptop Computer 15" — 256GB SSD / حاسوب محمول 15 بوصة',
            'hs_code_id': hs_map.get('8471.30', HSCode.search([], limit=1)).id,
            'country_origin_id': CN.id,
            'quantity': 200, 'uom_id': env.ref('uom.product_uom_unit').id,
            'unit_weight': 2.1, 'unit_value': 750.0,
            'saudi_vat_rate': 15.0, 'saudi_import_duty_rate': 5.0,
        },
        {
            'clearance_id': cl.id, 'sequence': 20,
            'description': 'Laptop Charger 65W / شاحن حاسوب 65 واط',
            'hs_code_id': hs_map.get('8471.30', HSCode.search([], limit=1)).id,
            'country_origin_id': CN.id,
            'quantity': 200, 'uom_id': env.ref('uom.product_uom_unit').id,
            'unit_weight': 0.35, 'unit_value': 45.0,
            'saudi_vat_rate': 15.0, 'saudi_import_duty_rate': 5.0,
        },
    ])

    # Duty lines
    cif = cl.cif_value
    env['customs.duty.line'].create([
        {
            'clearance_id': cl.id,
            'duty_type_id': dt_customs_5.id,
            'base_amount': cif, 'rate': 5.0,
            'payment_date': (date.today() - timedelta(days=2)).isoformat(),
            'payment_reference': 'SADAD-PAY-01',
        },
        {
            'clearance_id': cl.id,
            'duty_type_id': dt_vat_15.id,
            'base_amount': cif + (cif * 0.05), 'rate': 15.0,
            'payment_date': (date.today() - timedelta(days=2)).isoformat(),
            'payment_reference': 'SADAD-PAY-02',
        },
        {
            'clearance_id': cl.id,
            'duty_type_id': dt_port_fee.id,
            'base_amount': 0, 'rate': 0.0, 'is_percentage': False,
            'fixed_amount': 1200.0,
        },
    ])

    # Documents
    for doc_info in [
        (dt_bl,    'BL — MSCUJD2600001',    'MSCUJD2600001',  'verified'),
        (dt_inv,   'FATOORAH Invoice',       'FAT-INV-2026-8821', 'verified'),
        (dt_pl,    'Packing List',           'PL-CN-2026-441',    'verified'),
        (dt_coo,   'Certificate of Origin',  'COO-CN-2026-771',   'verified'),
        (dt_fasah, 'FASAH Declaration',      'FASAH-2026-JED-00123', 'verified'),
        (dt_acd,   'ACD Confirmation',       'ACD-2026-00445',    'verified'),
        (dt_saber_scoc, 'SABER SCoC',        'SABER-SCOC-99134',  'verified'),
        (dt_citc,  'CITC Certificate',       'CITC-2026-LAP-0012','verified'),
        (dt_release,'Release Permit',        'RELEASE-JED-2026-4521','verified'),
        (dt_sadad, 'SADAD Payment Receipt',  'SADAD-2026-PAY-33412','verified'),
    ]:
        if doc_info[0]:
            env['customs.document'].create({
                'clearance_id': cl.id,
                'document_type_id': doc_info[0].id,
                'name': doc_info[1],
                'document_number': doc_info[2],
                'issue_date': (date.today() - timedelta(days=6)).isoformat(),
                'state': doc_info[3],
            })

    print(f"  ✓ Order 1: {cl.name} — Import Green Lane RELEASED")
    return cl


# ────────────────────────────────────────────────────────────────────────────
# ORDER 2: Import — Yellow Lane — UNDER CUSTOMS REVIEW (mobile phones)
# ────────────────────────────────────────────────────────────────────────────
def create_clearance_2():
    existing = Clearance.search([('fasah_declaration_no', '=', 'FASAH-2026-RUH-00456')], limit=1)
    if existing:
        print("  - Order 2 already exists, skipping")
        return existing

    cl = Clearance.create({
        'clearance_type':      'import',
        'partner_id':          partner_tamimi.id,
        'broker_id':           broker_3.id,
        'port_id':             port_riyadh.id,
        'customs_office_id':   czat_riyadh.id,
        'country_origin_id':   CN.id,
        'date':                (date.today() - timedelta(days=2)).isoformat(),
        'shipment_id':         shipment_2.id,

        'fasah_declaration_no': 'FASAH-2026-RUH-00456',
        'acd_reference_no':     'ACD-2026-00612',
        'acd_submission_date':  (date.today() - timedelta(days=4)).isoformat(),
        'fatoorah_invoice_no':  'FAT-INV-2026-9034',
        'bill_of_lading_no':    'AWB-176-22341',

        'requires_saber': True,
        'saber_scoc_no':  'SABER-SCOC-88712',
        'saber_scoc_expiry': (date.today() + timedelta(days=60)).isoformat(),
        'saber_scoc_verified': True,
        'requires_citc':  True,
        'citc_certificate_no': 'CITC-2026-MOB-0088',
        'citc_approved':  True,

        'currency_id':    SAR.id,
        'goods_value':    95000.0,
        'freight_amount':  3200.0,
        'insurance_amount': 900.0,
        'service_fee':     2100.0,

        'inspection_lane': 'yellow',
        'payment_status':  'unpaid',
        'state':           'customs_review',
    })

    env['customs.clearance.line'].create({
        'clearance_id': cl.id, 'sequence': 10,
        'description': 'Smartphone Android 256GB / هاتف ذكي أندرويد 256 جيجا',
        'hs_code_id': hs_map.get('8517.12', HSCode.search([], limit=1)).id,
        'country_origin_id': CN.id,
        'quantity': 500, 'uom_id': env.ref('uom.product_uom_unit').id,
        'unit_weight': 0.22, 'unit_value': 190.0,
        'saudi_vat_rate': 15.0, 'saudi_import_duty_rate': 5.0,
    })

    cif = cl.cif_value
    env['customs.duty.line'].create([
        {'clearance_id': cl.id, 'duty_type_id': dt_customs_5.id, 'base_amount': cif, 'rate': 5.0},
        {'clearance_id': cl.id, 'duty_type_id': dt_vat_15.id,    'base_amount': cif + cif*0.05, 'rate': 15.0},
    ])

    for doc_info in [
        (dt_bl,    'AWB — SV-4421',        'AWB-176-22341',        'verified'),
        (dt_inv,   'Commercial Invoice',    'FAT-INV-2026-9034',    'verified'),
        (dt_pl,    'Packing List',          'PL-CN-2026-889',       'verified'),
        (dt_coo,   'Certificate of Origin', 'COO-CN-2026-334',      'received'),
        (dt_saber_scoc, 'SABER SCoC',       'SABER-SCOC-88712',     'verified'),
        (dt_citc,  'CITC Certificate',      'CITC-2026-MOB-0088',   'received'),
        (dt_acd,   'ACD Confirmation',      'ACD-2026-00612',       'verified'),
    ]:
        if doc_info[0]:
            env['customs.document'].create({
                'clearance_id': cl.id, 'document_type_id': doc_info[0].id,
                'name': doc_info[1], 'document_number': doc_info[2],
                'issue_date': (date.today() - timedelta(days=3)).isoformat(),
                'state': doc_info[3],
            })

    print(f"  ✓ Order 2: {cl.name} — Import Yellow Lane CUSTOMS REVIEW")
    return cl


# ────────────────────────────────────────────────────────────────────────────
# ORDER 3: Import — Red Lane — UNDER PHYSICAL INSPECTION (food — SFDA)
# ────────────────────────────────────────────────────────────────────────────
def create_clearance_3():
    existing = Clearance.search([('fasah_declaration_no', '=', 'FASAH-2026-DMM-00789')], limit=1)
    if existing:
        print("  - Order 3 already exists, skipping")
        return existing

    cl = Clearance.create({
        'clearance_type':      'import',
        'partner_id':          partner_almarai.id,
        'broker_id':           broker_2.id,
        'port_id':             port_dammam.id,
        'country_origin_id':   AE.id,
        'date':                (date.today() - timedelta(days=3)).isoformat(),

        'fasah_declaration_no': 'FASAH-2026-DMM-00789',
        'acd_reference_no':     'ACD-2026-00780',
        'acd_submission_date':  (date.today() - timedelta(days=5)).isoformat(),
        'bill_of_lading_no':    'BL-SAL-2026-0091',

        'requires_sfda':      True,
        'sfda_approval_no':   'SFDA-IMP-2026-BEEF-441',
        'sfda_approved':      True,

        'currency_id':        SAR.id,
        'goods_value':        67000.0,
        'freight_amount':      3800.0,
        'insurance_amount':    1100.0,
        'service_fee':         1800.0,
        'port_charges':         950.0,

        'inspection_lane':    'red',
        'payment_status':     'unpaid',
        'state':              'inspection',
        'zatca_remarks':      'Physical inspection assigned — Red Lane due to first-time import of this commodity class. Inspector: Officer Khalid Al-Otaibi. Inspection scheduled for tomorrow 09:00.',
    })

    env['customs.clearance.line'].create([
        {
            'clearance_id': cl.id, 'sequence': 10,
            'description': 'Fresh Chilled Beef — Halal Certified / لحم بقري طازج حلال',
            'hs_code_id': hs_map.get('0201.10', HSCode.search([], limit=1)).id,
            'country_origin_id': AE.id,
            'quantity': 12000.0, 'uom_id': env.ref('uom.product_uom_kgm').id,
            'unit_weight': 1.0, 'unit_value': 5.2,
            'saudi_vat_rate': 0.0, 'saudi_import_duty_rate': 5.0,
        },
    ])

    cif = cl.cif_value
    env['customs.duty.line'].create([
        {'clearance_id': cl.id, 'duty_type_id': dt_gcc_zero.id, 'base_amount': cif, 'rate': 0.0,
         'notes': 'GCC origin — 0% duty (UAE)'},
        {'clearance_id': cl.id, 'duty_type_id': dt_port_fee.id, 'base_amount': 0, 'rate': 0.0,
         'is_percentage': False, 'fixed_amount': 950.0},
    ])

    for doc_info in [
        (dt_bl,   'BL — SAL-2026-0091',   'BL-SAL-2026-0091',     'verified'),
        (dt_inv,  'Commercial Invoice',    'FAT-INV-2026-7721',     'verified'),
        (dt_pl,   'Packing List',          'PL-AE-2026-112',        'verified'),
        (dt_coo,  'GCC Certificate of Origin', 'COO-AE-2026-GCC-98','verified'),
        (dt_sfda, 'SFDA Halal Approval',   'SFDA-IMP-2026-BEEF-441','verified'),
        (dt_acd,  'ACD Confirmation',      'ACD-2026-00780',        'verified'),
    ]:
        if doc_info[0]:
            env['customs.document'].create({
                'clearance_id': cl.id, 'document_type_id': doc_info[0].id,
                'name': doc_info[1], 'document_number': doc_info[2],
                'issue_date': (date.today() - timedelta(days=4)).isoformat(),
                'state': doc_info[3],
            })

    print(f"  ✓ Order 3: {cl.name} — Import Red Lane PHYSICAL INSPECTION")
    return cl


# ────────────────────────────────────────────────────────────────────────────
# ORDER 4: Export — Green Lane — DELIVERED (industrial equipment to Germany)
# ────────────────────────────────────────────────────────────────────────────
def create_clearance_4():
    existing = Clearance.search([('fasah_declaration_no', '=', 'FASAH-2026-JED-EXP-0034')], limit=1)
    if existing:
        print("  - Order 4 already exists, skipping")
        return existing

    cl = Clearance.create({
        'clearance_type':       'export',
        'partner_id':           partner_sabic.id,
        'broker_id':            broker_1.id,
        'port_id':              port_jeddah.id,
        'customs_office_id':    czat_jeddah.id,
        'country_destination_id': DE.id,
        'date':                 (date.today() - timedelta(days=10)).isoformat(),
        'actual_clearance_date':(date.today() - timedelta(days=8)).isoformat(),

        'fasah_declaration_no': 'FASAH-2026-JED-EXP-0034',
        'acd_reference_no':     'ACD-2026-EXP-00221',
        'acd_submission_date':  (date.today() - timedelta(days=12)).isoformat(),
        'fatoorah_invoice_no':  'FAT-EXP-2026-3341',
        'bill_of_lading_no':    'HAPAG-2026-JED-0091',
        'sadad_payment_ref':    'SADAD-EXP-2026-0091',
        'release_permit_no':    'EXP-RELEASE-JED-2026-0034',
        'masar_tracking_no':    'MASAR-EXP-2026-0034',

        'is_aeo':               True,
        'aeo_certificate_no':   'AEO-KSA-2025-0089',

        'currency_id':          SAR.id,
        'goods_value':          340000.0,
        'freight_amount':        22000.0,
        'insurance_amount':       4500.0,
        'service_fee':            5200.0,

        'inspection_lane':      'green',
        'payment_status':       'paid',
        'state':                'delivered',
    })

    env['customs.clearance.line'].create([
        {
            'clearance_id': cl.id, 'sequence': 10,
            'description': 'Industrial Chemical Processing Equipment / معدات معالجة كيميائية صناعية',
            'country_origin_id': SA.id,
            'quantity': 3.0, 'uom_id': env.ref('uom.product_uom_unit').id,
            'unit_weight': 4200.0, 'unit_value': 112000.0,
            'saudi_vat_rate': 0.0, 'saudi_import_duty_rate': 0.0,
        },
    ])

    env['customs.duty.line'].create([
        {'clearance_id': cl.id, 'duty_type_id': dt_port_fee.id,
         'base_amount': 0, 'rate': 0.0, 'is_percentage': False, 'fixed_amount': 2200.0,
         'payment_reference': 'SADAD-EXP-2026-0091'},
    ])

    for doc_info in [
        (dt_bl,      'BL — HAPAG-2026-JED-0091',    'HAPAG-2026-JED-0091',  'verified'),
        (dt_inv,     'Export Commercial Invoice',    'FAT-EXP-2026-3341',     'verified'),
        (dt_pl,      'Export Packing List',          'PL-SA-EXP-2026-99',     'verified'),
        (dt_release, 'Export Release Permit',        'EXP-RELEASE-JED-2026-0034','verified'),
        (dt_acd,     'ACD Confirmation',             'ACD-2026-EXP-00221',    'verified'),
    ]:
        if doc_info[0]:
            env['customs.document'].create({
                'clearance_id': cl.id, 'document_type_id': doc_info[0].id,
                'name': doc_info[1], 'document_number': doc_info[2],
                'issue_date': (date.today() - timedelta(days=11)).isoformat(),
                'state': doc_info[3],
            })

    print(f"  ✓ Order 4: {cl.name} — Export DELIVERED to Germany")
    return cl


# ────────────────────────────────────────────────────────────────────────────
# ORDER 5: Import — DRAFT — ACD not yet submitted (new order to demonstrate)
# ────────────────────────────────────────────────────────────────────────────
def create_clearance_5():
    existing = Clearance.search([('partner_id', '=', partner_siemens.id),
                                  ('state', '=', 'draft')], limit=1)
    if existing:
        print("  - Order 5 already exists, skipping")
        return existing

    cl = Clearance.create({
        'clearance_type':       'import',
        'partner_id':           partner_siemens.id,
        'broker_id':            broker_3.id,
        'port_id':              port_jeddah.id,
        'country_origin_id':    DE.id,
        'date':                 date.today().isoformat(),
        'expected_clearance_date': (date.today() + timedelta(days=5)).isoformat(),

        'requires_saber':  True,
        'requires_citc':   True,

        'currency_id':     SAR.id,
        'goods_value':     420000.0,
        'freight_amount':   18000.0,
        'insurance_amount':  6000.0,
        'service_fee':       7500.0,

        'state':           'draft',
        'payment_status':  'unpaid',
        'internal_notes':  '<p>New shipment of industrial automation equipment from Siemens Germany. SABER certificates must be obtained before submission. Contact CITC for wireless module certification.</p>',
    })

    env['customs.clearance.line'].create([
        {
            'clearance_id': cl.id, 'sequence': 10,
            'description': 'Industrial PLC Controllers / وحدات التحكم المنطقية الصناعية',
            'country_origin_id': DE.id,
            'quantity': 50.0, 'uom_id': env.ref('uom.product_uom_unit').id,
            'unit_weight': 8.5, 'unit_value': 5600.0,
            'saudi_vat_rate': 15.0, 'saudi_import_duty_rate': 5.0,
            'requires_saber': True, 'requires_citc': True,
        },
        {
            'clearance_id': cl.id, 'sequence': 20,
            'description': 'Industrial Sensors & Actuators / حساسات ومشغلات صناعية',
            'country_origin_id': DE.id,
            'quantity': 200.0, 'uom_id': env.ref('uom.product_uom_unit').id,
            'unit_weight': 0.9, 'unit_value': 1200.0,
            'saudi_vat_rate': 15.0, 'saudi_import_duty_rate': 5.0,
        },
    ])

    print(f"  ✓ Order 5: {cl.name} — Import DRAFT (pending ACD + SABER)")
    return cl


# ── Execute all ───────────────────────────────────────────────────────────────
cl1 = create_clearance_1()
cl2 = create_clearance_2()
cl3 = create_clearance_3()
cl4 = create_clearance_4()
cl5 = create_clearance_5()

# Commit all changes
env.cr.commit()

print("\n" + "=" * 70)
print("  DEMO DATA CREATED SUCCESSFULLY")
print("=" * 70)
print(f"\n  Brokers created:          3")
print(f"  HS Codes created:         {len(hs_map)}")
print(f"  Clearance orders:         5")
print(f"    {cl1.name:<20} Green Lane — Released      (Laptops / Jeddah)")
print(f"    {cl2.name:<20} Yellow Lane — Under Review (Phones / Riyadh)")
print(f"    {cl3.name:<20} Red Lane — Inspection      (Food / Dammam)")
print(f"    {cl4.name:<20} Green Lane — Delivered     (Export / Germany)")
print(f"    {cl5.name:<20} Draft — Pending ACD        (Equipment / Jeddah)")
print(f"  Shipments:                2")
print(f"\n  Open Odoo → Customs Clearance KSA to see all data.")
print("=" * 70)
