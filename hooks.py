# -*- coding: utf-8 -*-
"""
hooks.py — Post-install hook for customs_clearance
===================================================
Runs automatically when the module is installed.
Creates all demo data using proper Odoo ORM methods.

To re-run after install:
  - Uninstall the module, reinstall it
  - Or upgrade with:  Apps → Customs Clearance → Upgrade
"""
import logging
from datetime import date, timedelta

_logger = logging.getLogger(__name__)

def post_migrate_hook(env, version):
    _fix_module_name_migration(env)
    _create_demo_data(env)
    _set_home_action(env)

def post_install_hook(env):
    """
    Entry point called by Odoo after module installation.
    Receives `env` — a fully functional Odoo Environment.
    """
    _logger.info("=== Customs Clearance: Running demo data hook ===")

    try:
        _fix_module_name_migration(env)
        _create_demo_data(env)
        _set_home_action(env)
        _logger.info("=== Customs Clearance: Demo data created successfully ===")
    except Exception as e:
        _logger.error("=== Customs Clearance: Demo data error: %s ===", str(e))
        # Do NOT raise — a failed hook should not block installation
        import traceback
        _logger.error(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# MODULE NAME MIGRATION
# ─────────────────────────────────────────────────────────────────────────────

def _fix_module_name_migration(env):
    """
    Migrate external IDs from old module name (customs_clearance_ksa) to new name (customs_clearance).
    This fixes the issue where security groups and other records were created with the old module prefix.
    Also removes conflicting action records.
    """
    _logger.info("=== Running module name migration: customs_clearance_ksa → customs_clearance ===")
    
    try:
        # Find all external IDs with the old module name
        IrModelData = env['ir.model.data']
        old_external_ids = IrModelData.search([
            ('module', '=', 'customs_clearance_ksa')
        ])
        
        if old_external_ids:
            _logger.info("  Found %d external IDs with old module name", len(old_external_ids))
            # Update them to use the new module name
            old_external_ids.write({'module': 'customs_clearance'})
            _logger.info("  ✓ Updated all external IDs to use 'customs_clearance' module name")
        else:
            _logger.info("  No old external IDs found - migration not needed")
        
        # Remove old conflicting action_customs_dashboard if it exists as wrong type
        try:
            old_action_data = IrModelData.search([
                ('module', '=', 'customs_clearance'),
                ('name', '=', 'action_customs_dashboard'),
                ('model', '=', 'ir.actions.act_window')
            ], limit=1)
            
            if old_action_data:
                _logger.info("  Found conflicting action_customs_dashboard (act_window) - removing...")
                # Get the actual record
                old_action = env['ir.actions.act_window'].browse(old_action_data.res_id)
                if old_action.exists():
                    old_action.unlink()
                old_action_data.unlink()
                _logger.info("  ✓ Removed conflicting action")
        except Exception as e:
            _logger.warning("  Could not remove old action: %s", str(e))
            
    except Exception as e:
        _logger.warning("  Migration warning: %s", str(e))
        # Don't fail the installation if migration has issues


# ─────────────────────────────────────────────────────────────────────────────
# HOME ACTION — set dashboard as default page after login
# ─────────────────────────────────────────────────────────────────────────────

def _set_home_action(env):
    """
    Sets the Customs Dashboard as the home page for all users after login.
    Uses res.users.action_id — the standard Odoo mechanism for per-user home actions.
    """
    try:
        action = env.ref('customs_clearance.action_customs_dashboard', raise_if_not_found=False)
        if not action:
            _logger.warning("_set_home_action: action_customs_dashboard not found yet — skipping")
            return

        # Apply to all existing users (skip system/portal users to be safe)
        users = env['res.users'].search([
            ('share', '=', False),       # internal users only
            ('active', '=', True),
        ])
        users.write({'action_id': action.id})
        _logger.info("  ✓ Set Customs Dashboard as home for %d users", len(users))

        # Set as system-wide default so new users also get it
        env['ir.default'].set('res.users', 'action_id', action.id)
        _logger.info("  ✓ Set Customs Dashboard as default home action for new users")

    except Exception as e:
        _logger.warning("  _set_home_action failed (non-blocking): %s", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_partner(env, name, country_code='SA', city=None, vat=None):
    Partner = env['res.partner']
    partner = Partner.search([('name', '=', name)], limit=1)
    if not partner:
        country = env['res.country'].search([('code', '=', country_code)], limit=1)
        vals = {
            'name':         name,
            'company_type': 'company',
            'country_id':   country.id if country else False,
        }
        if city:
            vals['city'] = city
        if vat:
            vals['vat'] = vat
        partner = Partner.create(vals)
        _logger.info("  Created partner: %s", name)
    return partner


def _get_country(env, code):
    if not code:
        return env['res.country'].browse()
    return env['res.country'].search([('code', '=', code)], limit=1)


def _get_currency(env, code='SAR'):
    return env['res.currency'].search([('name', '=', code)], limit=1)


def _get_port(env, port_code):
    return env['customs.port'].search([('code', '=', port_code)], limit=1)


def _get_duty_type(env, code):
    return env['customs.duty.type'].search([('code', '=', code)], limit=1)


def _get_doc_type(env, code):
    return env['customs.document.type'].search([('code', '=', code)], limit=1)


def _get_uom(env, ref):
    try:
        return env.ref(ref)
    except Exception:
        return env['uom.uom'].search([], limit=1)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DATA CREATION
# ─────────────────────────────────────────────────────────────────────────────

def _create_demo_data(env):
    today = date.today()

    # ── Countries ─────────────────────────────────────────────────────────────
    SA = _get_country(env, 'SA')
    CN = _get_country(env, 'CN')
    DE = _get_country(env, 'DE')
    AE = _get_country(env, 'AE')
    SAR = _get_currency(env, 'SAR')
    uom_unit = _get_uom(env, 'uom.product_uom_unit')
    uom_kg   = _get_uom(env, 'uom.product_uom_kgm')

    # ── Partners ──────────────────────────────────────────────────────────────
    _logger.info("  Creating partners...")
    partner_almarai = _get_or_create_partner(env, 'Al Marai Company / شركة المراعي',    city='Riyadh',  vat='3000000001')
    partner_sabic   = _get_or_create_partner(env, 'SABIC — Saudi Basic Industries',      city='Riyadh',  vat='3000000002')
    partner_tamimi  = _get_or_create_partner(env, 'Tamimi Markets / أسواق التميمي',      city='Dammam',  vat='3000000003')
    partner_siemens = _get_or_create_partner(env, 'Siemens Saudi Arabia',                city='Jeddah',  vat='3000000004')

    broker_p1 = _get_or_create_partner(env, 'Abdullah Al-Rashidi Customs Clearance', city='Jeddah')
    broker_p2 = _get_or_create_partner(env, 'Gulf Clearance Services',               city='Dammam')
    broker_p3 = _get_or_create_partner(env, 'Royal Star Customs Brokers',            city='Riyadh')

    # ── Brokers ───────────────────────────────────────────────────────────────
    _logger.info("  Creating brokers...")
    Broker = env['customs.broker']

    def _make_broker(name, partner, license_no, zatca_code, fasah_user, days, aeo=False):
        b = Broker.search([('license_number', '=', license_no)], limit=1)
        if not b:
            b = Broker.create({
                'name':                name,
                'partner_id':          partner.id,
                'license_number':      license_no,
                'license_expiry_date': (today + timedelta(days=days)).isoformat(),
                'zatca_broker_code':   zatca_code,
                'fasah_username':      fasah_user,
                'specialization':      'both',
                'service_fee_type':    'percentage',
                'service_fee':         1.5,
                'is_aeo_broker':       aeo,
                'aeo_cert_no':         ('AEO-%s-2025' % zatca_code) if aeo else False,
            })
            _logger.info("    Broker: %s", name)
        return b

    broker_1 = _make_broker('Abdullah Al-Rashidi Customs Clearance', broker_p1, 'KSA-BRK-10234', 'ZATCA-BR-1234', 'alrashidi_fasah', 365, aeo=True)
    broker_2 = _make_broker('Gulf Clearance Services',               broker_p2, 'KSA-BRK-20891', 'ZATCA-BR-2089', 'gulf_clr_fasah',  180)
    broker_3 = _make_broker('Royal Star Customs Brokers',            broker_p3, 'KSA-BRK-30456', 'ZATCA-BR-3045', 'royalstar_fasah', 730)

    # ── HS Codes ──────────────────────────────────────────────────────────────
    _logger.info("  Creating HS codes...")
    HSCode = env['customs.hs.code']

    hs_data = [
        {'code': '8471.30', 'name': 'Laptop Computers', 'name_ar': 'أجهزة الحاسوب المحمولة',
         'import_duty_rate': 5.0,   'vat_rate': 15.0, 'excise_rate': 0.0,
         'requires_saber': True,  'requires_citc': True,  'requires_sfda': False, 'category': 'Electronics'},
        {'code': '0201.10', 'name': 'Beef — fresh or chilled', 'name_ar': 'لحم البقر الطازج',
         'import_duty_rate': 5.0,   'vat_rate': 0.0,  'excise_rate': 0.0,
         'requires_saber': False, 'requires_citc': False, 'requires_sfda': True,  'category': 'Food'},
        {'code': '2402.20', 'name': 'Cigarettes containing tobacco', 'name_ar': 'سجائر',
         'import_duty_rate': 100.0, 'vat_rate': 15.0, 'excise_rate': 100.0,
         'requires_saber': False, 'requires_citc': False, 'requires_sfda': False,
         'is_restricted': True, 'category': 'Tobacco'},
        {'code': '8517.12', 'name': 'Mobile phones', 'name_ar': 'الهواتف المحمولة',
         'import_duty_rate': 5.0,   'vat_rate': 15.0, 'excise_rate': 0.0,
         'requires_saber': True,  'requires_citc': True,  'requires_sfda': False, 'category': 'Telecom'},
        {'code': '3004.50', 'name': 'Medicaments — vitamins', 'name_ar': 'أدوية فيتامينات',
         'import_duty_rate': 0.0,   'vat_rate': 0.0,  'excise_rate': 0.0,
         'requires_saber': False, 'requires_citc': False, 'requires_sfda': True,  'category': 'Pharma'},
        {'code': '8703.23', 'name': 'Motor cars 1000-1500cc', 'name_ar': 'سيارات ركاب',
         'import_duty_rate': 12.0,  'vat_rate': 15.0, 'excise_rate': 0.0,
         'requires_saber': True,  'requires_citc': False, 'requires_sfda': False, 'category': 'Automotive'},
    ]

    hs_map = {}
    for h in hs_data:
        hs = HSCode.search([('code', '=', h['code'])], limit=1)
        if not hs:
            hs = HSCode.create(h)
            _logger.info("    HS Code %s: %s", h['code'], h['name'])
        hs_map[h['code']] = hs

    # ── Ports lookup (pre-loaded by data XML) ──────────────────────────────
    port_jeddah  = _get_port(env, 'SAJED')
    port_dammam  = _get_port(env, 'SADMM')
    port_riyadh  = _get_port(env, 'SARUH')
    czat_jeddah  = _get_port(env, 'CZATJED')
    czat_riyadh  = _get_port(env, 'CZATRUH')

    # ── Duty types lookup ──────────────────────────────────────────────────
    dt_customs_5  = _get_duty_type(env, 'KSA-CD-5')
    dt_vat_15     = _get_duty_type(env, 'KSA-VAT-15')
    dt_port_fee   = _get_duty_type(env, 'KSA-PSF')
    dt_gcc_zero   = _get_duty_type(env, 'KSA-GCC-0')

    # ── Document types lookup ──────────────────────────────────────────────
    dt_bl         = _get_doc_type(env, 'BL')
    dt_inv        = _get_doc_type(env, 'INV')
    dt_pl         = _get_doc_type(env, 'PL')
    dt_coo        = _get_doc_type(env, 'COO')
    dt_fasah      = _get_doc_type(env, 'FASAH-DEC')
    dt_acd        = _get_doc_type(env, 'ACD')
    dt_saber_scoc = _get_doc_type(env, 'SABER-SCOC')
    dt_sfda       = _get_doc_type(env, 'SFDA')
    dt_citc       = _get_doc_type(env, 'CITC')
    dt_release    = _get_doc_type(env, 'RELEASE')
    dt_sadad      = _get_doc_type(env, 'SADAD')

    # ── Shipments ─────────────────────────────────────────────────────────
    _logger.info("  Creating shipments...")
    Shipment = env['customs.shipment']

    def _make_shipment(name, stype, vessel, voyage, bl, origin_code, dest_code):
        s = Shipment.search([('name', '=', name)], limit=1)
        if not s:
            port_origin = _get_port(env, origin_code)
            port_dest   = _get_port(env, dest_code)
            s = Shipment.create({
                'name':                name,
                'shipment_type':       stype,
                'vessel_name':         vessel,
                'voyage_number':       voyage,
                'bill_of_lading_no':   bl,
                'port_origin_id':      port_origin.id if port_origin else False,
                'port_destination_id': port_dest.id   if port_dest   else False,
                'departure_date':      (today - timedelta(days=12)).isoformat(),
                'eta':                 (today - timedelta(days=2)).isoformat(),
                'actual_arrival_date': (today - timedelta(days=1)).isoformat(),
                'shipper_id':          broker_p1.id,
                'consignee_id':        partner_almarai.id,
                'gross_weight':        18500.0,
                'volume':              42.5,
                'packages_count':      320,
                'state':               'arrived',
            })
            # Container
            env['customs.container'].create({
                'shipment_id':      s.id,
                'container_number': 'MSCU%s1234' % name[-4:],
                'container_type':   '40hc',
                'seal_number':      'SEAL%s001' % name[-4:],
                'gross_weight':     18500.0,
                'volume':           67.7,
            })
            _logger.info("    Shipment: %s", name)
        return s

    shipment_1 = _make_shipment('SHP/2026/0001', 'sea', 'MSC DIANA',    'MD-1142W', 'MSCUJD2600001', 'SAJED', 'SAJED')
    shipment_2 = _make_shipment('SHP/2026/0002', 'air', 'Saudia Cargo', 'SV-4421',  'AWB-176-22341', 'SARUH', 'SARUH')

    # ── Clearance Orders ───────────────────────────────────────────────────
    _logger.info("  Creating clearance orders...")
    Clearance = env['customs.clearance']

    def _add_docs(cl, doc_list):
        for doc_type, name, number, state in doc_list:
            if doc_type:
                env['customs.document'].create({
                    'clearance_id':      cl.id,
                    'document_type_id':  doc_type.id,
                    'name':              name,
                    'document_number':   number,
                    'issue_date':        (today - timedelta(days=6)).isoformat(),
                    'state':             state,
                })

    # ── Order 1: Import — Green Lane — Released ──────────────────────────
    if not Clearance.search([('fasah_declaration_no', '=', 'FASAH-2026-JED-00123')], limit=1):
        cl1 = Clearance.create({
            'clearance_type':        'import',
            'partner_id':            partner_almarai.id,
            'broker_id':             broker_1.id,
            'port_id':               port_jeddah.id if port_jeddah else False,
            'customs_office_id':     czat_jeddah.id if czat_jeddah else False,
            'country_origin_id':     CN.id if CN else False,
            'date':                  (today - timedelta(days=5)).isoformat(),
            'expected_clearance_date': (today - timedelta(days=1)).isoformat(),
            'actual_clearance_date': (today - timedelta(days=1)).isoformat(),
            'shipment_id':           shipment_1.id,
            'fasah_declaration_no':  'FASAH-2026-JED-00123',
            'acd_reference_no':      'ACD-2026-00445',
            'acd_submission_date':   (today - timedelta(days=7)).isoformat(),
            'fatoorah_invoice_no':   'FAT-INV-2026-8821',
            'bill_of_lading_no':     'MSCUJD2600001',
            'customs_declaration_no':'BYN-2026-JED-9001',
            'sadad_payment_ref':     'SADAD-2026-PAY-33412',
            'release_permit_no':     'RELEASE-JED-2026-4521',
            'masar_tracking_no':     'MASAR-JED-2026-7712',
            'release_date':          (today - timedelta(days=1)).isoformat(),
            'requires_saber':        True,
            'saber_pcoc_no':         'SABER-PCOC-47821',
            'saber_scoc_no':         'SABER-SCOC-99134',
            'saber_scoc_expiry':     (today + timedelta(days=90)).isoformat(),
            'saber_scoc_verified':   True,
            'requires_citc':         True,
            'citc_certificate_no':   'CITC-2026-LAP-0012',
            'citc_approved':         True,
            'is_aeo':                True,
            'aeo_certificate_no':    'AEO-KSA-2025-0089',
            'currency_id':           SAR.id if SAR else False,
            'goods_value':           185000.0,
            'freight_amount':        8500.0,
            'insurance_amount':      2200.0,
            'service_fee':           3900.0,
            'port_charges':          1200.0,
            'inspection_lane':       'green',
            'payment_status':        'paid',
            'state':                 'released',
        })
        env['customs.clearance.line'].create([
            {
                'clearance_id':   cl1.id,
                'sequence':       10,
                'description':    'Laptop Computer 15" — 256GB SSD / حاسوب محمول',
                'hs_code_id':     hs_map.get('8471.30', HSCode.search([], limit=1)).id,
                'country_origin_id': CN.id if CN else False,
                'quantity':       200.0,
                'uom_id':         uom_unit.id if uom_unit else False,
                'unit_weight':    2.1,
                'unit_value':     750.0,
                'saudi_vat_rate': 15.0,
            },
            {
                'clearance_id':   cl1.id,
                'sequence':       20,
                'description':    'Laptop Charger 65W / شاحن حاسوب',
                'hs_code_id':     hs_map.get('8471.30', HSCode.search([], limit=1)).id,
                'country_origin_id': CN.id if CN else False,
                'quantity':       200.0,
                'uom_id':         uom_unit.id if uom_unit else False,
                'unit_weight':    0.35,
                'unit_value':     45.0,
                'saudi_vat_rate': 15.0,
            },
        ])
        cif = cl1.cif_value
        env['customs.duty.line'].create([
            {'clearance_id': cl1.id, 'duty_type_id': dt_customs_5.id if dt_customs_5 else False,
             'base_amount': cif, 'rate': 5.0,
             'payment_date': (today - timedelta(days=2)).isoformat(), 'payment_reference': 'SADAD-PAY-01'},
            {'clearance_id': cl1.id, 'duty_type_id': dt_vat_15.id if dt_vat_15 else False,
             'base_amount': cif + (cif * 0.05), 'rate': 15.0,
             'payment_date': (today - timedelta(days=2)).isoformat(), 'payment_reference': 'SADAD-PAY-02'},
            {'clearance_id': cl1.id, 'duty_type_id': dt_port_fee.id if dt_port_fee else False,
             'base_amount': 0, 'rate': 0.0, 'fixed_amount': 1200.0},
        ])
        _add_docs(cl1, [
            (dt_bl,         'BL — MSCUJD2600001',       'MSCUJD2600001',           'verified'),
            (dt_inv,        'FATOORAH Invoice',           'FAT-INV-2026-8821',       'verified'),
            (dt_pl,         'Packing List',               'PL-CN-2026-441',          'verified'),
            (dt_coo,        'Certificate of Origin',      'COO-CN-2026-771',         'verified'),
            (dt_fasah,      'FASAH Declaration',          'FASAH-2026-JED-00123',    'verified'),
            (dt_acd,        'ACD Confirmation',           'ACD-2026-00445',          'verified'),
            (dt_saber_scoc, 'SABER SCoC',                 'SABER-SCOC-99134',        'verified'),
            (dt_citc,       'CITC Certificate',           'CITC-2026-LAP-0012',      'verified'),
            (dt_release,    'Release Permit',             'RELEASE-JED-2026-4521',   'verified'),
            (dt_sadad,      'SADAD Payment Receipt',      'SADAD-2026-PAY-33412',    'verified'),
        ])
        _logger.info("    Order 1: %s — Import Green Lane RELEASED", cl1.name)

    # ── Order 2: Import — Yellow Lane — Customs Review ───────────────────
    if not Clearance.search([('fasah_declaration_no', '=', 'FASAH-2026-RUH-00456')], limit=1):
        cl2 = Clearance.create({
            'clearance_type':       'import',
            'partner_id':           partner_tamimi.id,
            'broker_id':            broker_3.id,
            'port_id':              port_riyadh.id if port_riyadh else False,
            'country_origin_id':    CN.id if CN else False,
            'date':                 (today - timedelta(days=2)).isoformat(),
            'shipment_id':          shipment_2.id,
            'fasah_declaration_no': 'FASAH-2026-RUH-00456',
            'acd_reference_no':     'ACD-2026-00612',
            'acd_submission_date':  (today - timedelta(days=4)).isoformat(),
            'fatoorah_invoice_no':  'FAT-INV-2026-9034',
            'bill_of_lading_no':    'AWB-176-22341',
            'requires_saber':       True,
            'saber_scoc_no':        'SABER-SCOC-88712',
            'saber_scoc_expiry':    (today + timedelta(days=60)).isoformat(),
            'saber_scoc_verified':  True,
            'requires_citc':        True,
            'citc_certificate_no':  'CITC-2026-MOB-0088',
            'citc_approved':        True,
            'currency_id':          SAR.id if SAR else False,
            'goods_value':          95000.0,
            'freight_amount':       3200.0,
            'insurance_amount':     900.0,
            'service_fee':          2100.0,
            'inspection_lane':      'yellow',
            'payment_status':       'unpaid',
            'state':                'customs_review',
        })
        env['customs.clearance.line'].create({
            'clearance_id':   cl2.id,
            'sequence':       10,
            'description':    'Smartphone Android 256GB / هاتف ذكي',
            'hs_code_id':     hs_map.get('8517.12', HSCode.search([], limit=1)).id,
            'country_origin_id': CN.id if CN else False,
            'quantity':       500.0,
            'uom_id':         uom_unit.id if uom_unit else False,
            'unit_weight':    0.22,
            'unit_value':     190.0,
            'saudi_vat_rate': 15.0,
        })
        cif2 = cl2.cif_value
        env['customs.duty.line'].create([
            {'clearance_id': cl2.id, 'duty_type_id': dt_customs_5.id if dt_customs_5 else False, 'base_amount': cif2, 'rate': 5.0},
            {'clearance_id': cl2.id, 'duty_type_id': dt_vat_15.id    if dt_vat_15    else False, 'base_amount': cif2 + cif2 * 0.05, 'rate': 15.0},
        ])
        _add_docs(cl2, [
            (dt_bl,         'AWB — SV-4421',            'AWB-176-22341',            'verified'),
            (dt_inv,        'Commercial Invoice',        'FAT-INV-2026-9034',        'verified'),
            (dt_pl,         'Packing List',              'PL-CN-2026-889',           'verified'),
            (dt_coo,        'Certificate of Origin',     'COO-CN-2026-334',          'received'),
            (dt_saber_scoc, 'SABER SCoC',                'SABER-SCOC-88712',         'verified'),
            (dt_citc,       'CITC Certificate',          'CITC-2026-MOB-0088',       'received'),
            (dt_acd,        'ACD Confirmation',          'ACD-2026-00612',           'verified'),
        ])
        _logger.info("    Order 2: %s — Import Yellow Lane CUSTOMS REVIEW", cl2.name)

    # ── Order 3: Import — Red Lane — Physical Inspection (food/SFDA) ─────
    if not Clearance.search([('fasah_declaration_no', '=', 'FASAH-2026-DMM-00789')], limit=1):
        cl3 = Clearance.create({
            'clearance_type':       'import',
            'partner_id':           partner_almarai.id,
            'broker_id':            broker_2.id,
            'port_id':              port_dammam.id if port_dammam else False,
            'country_origin_id':    AE.id if AE else False,
            'date':                 (today - timedelta(days=3)).isoformat(),
            'fasah_declaration_no': 'FASAH-2026-DMM-00789',
            'acd_reference_no':     'ACD-2026-00780',
            'acd_submission_date':  (today - timedelta(days=5)).isoformat(),
            'bill_of_lading_no':    'BL-SAL-2026-0091',
            'requires_sfda':        True,
            'sfda_approval_no':     'SFDA-IMP-2026-BEEF-441',
            'sfda_approved':        True,
            'currency_id':          SAR.id if SAR else False,
            'goods_value':          67000.0,
            'freight_amount':       3800.0,
            'insurance_amount':     1100.0,
            'service_fee':          1800.0,
            'port_charges':         950.0,
            'inspection_lane':      'red',
            'payment_status':       'unpaid',
            'state':                'inspection',
            'zatca_remarks':        'Red Lane — First-time import of this commodity. Physical inspection scheduled.',
        })
        env['customs.clearance.line'].create({
            'clearance_id':   cl3.id,
            'sequence':       10,
            'description':    'Fresh Chilled Beef — Halal Certified / لحم بقري طازج حلال',
            'hs_code_id':     hs_map.get('0201.10', HSCode.search([], limit=1)).id,
            'country_origin_id': AE.id if AE else False,
            'quantity':       12000.0,
            'uom_id':         uom_kg.id if uom_kg else False,
            'unit_weight':    1.0,
            'unit_value':     5.2,
            'saudi_vat_rate': 0.0,
        })
        cif3 = cl3.cif_value
        env['customs.duty.line'].create([
            {'clearance_id': cl3.id, 'duty_type_id': dt_gcc_zero.id  if dt_gcc_zero  else False, 'base_amount': cif3, 'rate': 0.0, 'notes': 'GCC origin — 0% duty (UAE)'},
            {'clearance_id': cl3.id, 'duty_type_id': dt_port_fee.id  if dt_port_fee  else False, 'base_amount': 0, 'rate': 0.0, 'fixed_amount': 950.0},
        ])
        _add_docs(cl3, [
            (dt_bl,   'BL — SAL-2026-0091',         'BL-SAL-2026-0091',         'verified'),
            (dt_inv,  'Commercial Invoice',           'FAT-INV-2026-7721',        'verified'),
            (dt_pl,   'Packing List',                 'PL-AE-2026-112',           'verified'),
            (dt_coo,  'GCC Certificate of Origin',    'COO-AE-2026-GCC-98',       'verified'),
            (dt_sfda, 'SFDA Halal Approval',          'SFDA-IMP-2026-BEEF-441',   'verified'),
            (dt_acd,  'ACD Confirmation',             'ACD-2026-00780',           'verified'),
        ])
        _logger.info("    Order 3: %s — Import Red Lane INSPECTION", cl3.name)

    # ── Order 4: Export — Green Lane — Delivered ─────────────────────────
    if not Clearance.search([('fasah_declaration_no', '=', 'FASAH-2026-JED-EXP-0034')], limit=1):
        cl4 = Clearance.create({
            'clearance_type':         'export',
            'partner_id':             partner_sabic.id,
            'broker_id':              broker_1.id,
            'port_id':                port_jeddah.id if port_jeddah else False,
            'customs_office_id':      czat_jeddah.id if czat_jeddah else False,
            'country_destination_id': DE.id if DE else False,
            'date':                   (today - timedelta(days=10)).isoformat(),
            'actual_clearance_date':  (today - timedelta(days=8)).isoformat(),
            'fasah_declaration_no':   'FASAH-2026-JED-EXP-0034',
            'acd_reference_no':       'ACD-2026-EXP-00221',
            'acd_submission_date':    (today - timedelta(days=12)).isoformat(),
            'fatoorah_invoice_no':    'FAT-EXP-2026-3341',
            'bill_of_lading_no':      'HAPAG-2026-JED-0091',
            'sadad_payment_ref':      'SADAD-EXP-2026-0091',
            'release_permit_no':      'EXP-RELEASE-JED-2026-0034',
            'masar_tracking_no':      'MASAR-EXP-2026-0034',
            'is_aeo':                 True,
            'aeo_certificate_no':     'AEO-KSA-2025-0089',
            'currency_id':            SAR.id if SAR else False,
            'goods_value':            340000.0,
            'freight_amount':         22000.0,
            'insurance_amount':       4500.0,
            'service_fee':            5200.0,
            'inspection_lane':        'green',
            'payment_status':         'paid',
            'state':                  'delivered',
        })
        env['customs.clearance.line'].create({
            'clearance_id':   cl4.id,
            'sequence':       10,
            'description':    'Industrial Chemical Processing Equipment / معدات معالجة كيميائية',
            'country_origin_id': SA.id if SA else False,
            'quantity':       3.0,
            'uom_id':         uom_unit.id if uom_unit else False,
            'unit_weight':    4200.0,
            'unit_value':     112000.0,
            'saudi_vat_rate': 0.0,
        })
        env['customs.duty.line'].create({
            'clearance_id': cl4.id,
            'duty_type_id': dt_port_fee.id if dt_port_fee else False,
            'base_amount': 0, 'rate': 0.0, 'fixed_amount': 2200.0,
            'payment_reference': 'SADAD-EXP-2026-0091',
        })
        _add_docs(cl4, [
            (dt_bl,      'BL — HAPAG-2026-JED-0091', 'HAPAG-2026-JED-0091',       'verified'),
            (dt_inv,     'Export Invoice',             'FAT-EXP-2026-3341',         'verified'),
            (dt_pl,      'Export Packing List',        'PL-SA-EXP-2026-99',         'verified'),
            (dt_release, 'Export Release Permit',      'EXP-RELEASE-JED-2026-0034', 'verified'),
            (dt_acd,     'ACD Confirmation',           'ACD-2026-EXP-00221',        'verified'),
        ])
        _logger.info("    Order 4: %s — Export DELIVERED to Germany", cl4.name)

    # ── Order 5: Import — Draft (new order, pending start) ────────────────
    if not Clearance.search([('partner_id', '=', partner_siemens.id), ('state', '=', 'draft')], limit=1):
        cl5 = Clearance.create({
            'clearance_type':         'import',
            'partner_id':             partner_siemens.id,
            'broker_id':              broker_3.id,
            'port_id':                port_jeddah.id if port_jeddah else False,
            'country_origin_id':      DE.id if DE else False,
            'date':                   today.isoformat(),
            'expected_clearance_date':(today + timedelta(days=5)).isoformat(),
            'requires_saber':         True,
            'requires_citc':          True,
            'currency_id':            SAR.id if SAR else False,
            'goods_value':            420000.0,
            'freight_amount':         18000.0,
            'insurance_amount':       6000.0,
            'service_fee':            7500.0,
            'state':                  'draft',
            'payment_status':         'unpaid',
            'internal_notes':         '<p><b>New shipment:</b> Industrial automation from Siemens Germany. SABER + CITC certificates required before submission.</p>',
        })
        env['customs.clearance.line'].create([
            {
                'clearance_id':   cl5.id,
                'sequence':       10,
                'description':    'Industrial PLC Controllers / وحدات التحكم المنطقية',
                'country_origin_id': DE.id if DE else False,
                'quantity':       50.0,
                'uom_id':         uom_unit.id if uom_unit else False,
                'unit_weight':    8.5,
                'unit_value':     5600.0,
                'saudi_vat_rate': 15.0,
            },
            {
                'clearance_id':   cl5.id,
                'sequence':       20,
                'description':    'Industrial Sensors / حساسات صناعية',
                'country_origin_id': DE.id if DE else False,
                'quantity':       200.0,
                'uom_id':         uom_unit.id if uom_unit else False,
                'unit_weight':    0.9,
                'unit_value':     1200.0,
                'saudi_vat_rate': 15.0,
            },
        ])
        _logger.info("    Order 5: %s — Import DRAFT (pending ACD + SABER)", cl5.name)

    _logger.info("  All demo data created successfully.")
