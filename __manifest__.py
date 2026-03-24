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
    'depends': ['base', 'mail', 'stock', 'account', 'purchase', 'product','website'],
    'data': [
        # security
        'security/customs_clearance_security.xml',
        'security/ir.model.access.csv',
        # data
        'data/customs_sequence_data.xml',
        'data/customs_saudi_ports_data.xml',
        'data/customs_document_type_data.xml',
        'data/customs_duty_type_data.xml',
        # views
        'views/customs_port_views.xml',
        'views/customs_broker_views.xml',
        'views/customs_hs_code_views.xml',
        'views/customs_duty_views.xml',
        'views/customs_document_views.xml',
        'views/customs_shipment_views.xml',
        'views/customs_clearance_views.xml',
        'views/customs_portal_request_views.xml', # backend review UI + email templates
        'views/customs_dashboard_views.xml',


        # Portal QWeb templates (served by portal_controller.py)
        'templates/portal_templates.xml',

        # Wizard + Menu
        'wizard/customs_compliance_wizard_views.xml',
        'views/customs_menu_views.xml',

        # reports
        'report/customs_clearance_report.xml',
        'report/customs_clearance_report_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'customs_clearance_ksa/static/src/components/**/*.js',
            'customs_clearance_ksa/static/src/components/**/*.xml',
            'customs_clearance_ksa/static/src/css/dashboard.scss',
            'customs_clearance_ksa/static/src/scss/customs_clearance_views.scss',
        ],
    },
    'post_init_hook': 'post_install_hook',
    'post_migrate_hook': 'post_migrate_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
