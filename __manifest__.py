# -*- coding: utf-8 -*-
{
    'name': 'Customs Clearance KSA — تخليص جمركي (المملكة العربية السعودية)',
    'version': '17.0.2.0.0',
    'category': 'Inventory/Logistics',
    'summary': 'Saudi Arabia Customs Clearance — ZATCA / FASAH / SABER Compliant',
    'description': """
Saudi Arabia Customs Clearance System — v2.0
=============================================
Fully aligned with ZATCA workflows.
New: FASAH, SABER, ACD, 3-lane risk, SADAD, FATOORAH, AEO, Saudi ports & duties.
    """,
    'author': 'YASSER & OMAR',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'stock', 'account', 'purchase', 'product', 'website', 'base_setup'],
    'data': [
        # security
        'security/customs_clearance_security.xml',
        'security/ir.model.access.csv',
        # data
        'data/customs_sequence_data.xml',
        'data/customs_saudi_ports_data.xml',
        'data/customs_document_type_data.xml',
        'data/customs_duty_type_data.xml',
        'data/customs_extended_sequences.xml',          # NEW: Bond, Penalty, Invoice sequences
        'data/customs_email_templates.xml',             # NEW: State-change & invoice email templates
        # views
        'views/customs_port_views.xml',
        'views/customs_broker_views.xml',
        'views/customs_hs_code_views.xml',
        'views/customs_duty_views.xml',
        'views/customs_document_views.xml',
        'views/customs_shipment_views.xml',
        'views/customs_clearance_views.xml',
        'views/customs_portal_request_views.xml',
        'views/customs_dashboard_views.xml',
        'views/customs_dashboard_action.xml',
        'views/customs_vip_views.xml',                  # NEW: VIP / AEO customers
        'views/customs_service_invoice_views.xml',      # NEW: Client service invoices
        'views/customs_bond_views.xml',                 # NEW: Customs bonds / guarantees
        'views/customs_penalty_views.xml',              # NEW: Penalties & appeals
        'views/customs_clearance_ext_views.xml',        # NEW: Clearance form extensions
        'views/customs_shipment_cost_views.xml',        # NEW: Shipment cost lines
        'views/whatsapp_settings_views.xml',            # NEW: WhatsApp notification settings

        # Portal QWeb templates
        'templates/portal_templates.xml',
        'templates/portal_tracking_templates.xml',      # NEW: Live tracking + invoice preview
        'templates/portal_tracking_detail.xml',         # NEW: Modern shipment tracking dashboard
        'templates/homepage_gateway.xml',               # NEW: Gateway homepage (2 buttons)
        'templates/portal_contract_template.xml',       # NEW: Printable service contract page

        # Wizard + Menu
        'wizard/customs_compliance_wizard_views.xml',
        'views/customs_menu_views.xml',

        # reports
        'report/customs_clearance_report.xml',
        'report/customs_clearance_report_template.xml',
        'report/customs_service_invoice_report.xml',
        'report/customs_service_invoice_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'customs_clearance/static/src/components/**/*.js',
            'customs_clearance/static/src/components/**/*.xml',
            'customs_clearance/static/src/css/dashboard.scss',
            'customs_clearance/static/src/css/dashboard_enhanced.scss',
            'customs_clearance/static/src/scss/customs_clearance_views.scss',
        ],
    },
    'post_init_hook': 'post_install_hook',
    'post_migrate_hook': 'post_migrate_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
