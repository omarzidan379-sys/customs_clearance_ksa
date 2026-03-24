# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class CustomsComplianceWizard(models.TransientModel):
    _name = 'customs.compliance.wizard'
    _description = 'Saudi Customs Compliance Checklist Wizard'

    clearance_id = fields.Many2one('customs.clearance', string='Clearance Order', required=True)
    clearance_type = fields.Selection(related='clearance_id.clearance_type')

    # ACD
    acd_submitted         = fields.Boolean(string='ACD submitted 24h before departure')
    acd_reference_no      = fields.Char(string='ACD Reference No.')

    # FASAH
    fasah_account_active  = fields.Boolean(string='FASAH account active (CR + VAT linked)')
    fasah_declaration_no  = fields.Char(string='FASAH Declaration No.')

    # Documents
    has_commercial_invoice= fields.Boolean(string='Commercial Invoice (FATOORAH compliant)')
    has_bill_of_lading    = fields.Boolean(string='Bill of Lading / Airway Bill')
    has_packing_list      = fields.Boolean(string='Packing List')
    has_coo               = fields.Boolean(string='Certificate of Origin (stamped + attested)')
    fatoorah_invoice_no   = fields.Char(string='FATOORAH Invoice No.')

    # SABER
    needs_saber           = fields.Boolean(string='Goods require SABER certificate?')
    saber_pcoc_obtained   = fields.Boolean(string='SABER PCoC obtained')
    saber_scoc_obtained   = fields.Boolean(string='SABER SCoC obtained')
    saber_scoc_no         = fields.Char(string='SABER SCoC No.')
    saber_scoc_expiry     = fields.Date(string='SCoC Expiry Date')

    # Regulatory
    needs_sfda            = fields.Boolean(string='Goods require SFDA approval?')
    sfda_approval_no      = fields.Char(string='SFDA Approval No.')
    sfda_approved         = fields.Boolean(string='SFDA Approval obtained')

    needs_citc            = fields.Boolean(string='Goods require CITC certificate?')
    citc_certificate_no   = fields.Char(string='CITC Certificate No.')
    citc_approved         = fields.Boolean(string='CITC Certificate obtained')

    needs_saso            = fields.Boolean(string='Goods require SASO certificate?')
    saso_certificate_no   = fields.Char(string='SASO Certificate No.')
    saso_approved         = fields.Boolean(string='SASO Certificate obtained')

    needs_moi             = fields.Boolean(string='Goods require MoI permit?')
    moi_permit_no         = fields.Char(string='MoI Permit No.')
    moi_approved          = fields.Boolean(string='MoI Permit obtained')

    # Duties
    duties_calculated     = fields.Boolean(string='All duties and taxes calculated in FASAH')
    sadad_payment_ref     = fields.Char(string='SADAD Payment Reference')
    payment_confirmed     = fields.Boolean(string='Payment confirmed')

    # Release
    release_permit_no     = fields.Char(string='Release Permit No. (إذن الإفراج)')
    masar_tracking_no     = fields.Char(string='MASAR Tracking No.')

    compliance_score      = fields.Integer(string='Compliance Score (%)', compute='_compute_score')
    compliance_summary    = fields.Text(string='Summary', compute='_compute_score')

    @api.depends(
        'acd_submitted', 'fasah_account_active', 'has_commercial_invoice',
        'has_bill_of_lading', 'has_packing_list', 'has_coo',
        'needs_saber', 'saber_scoc_obtained',
        'needs_sfda', 'sfda_approved',
        'needs_citc', 'citc_approved',
        'needs_saso', 'saso_approved',
        'needs_moi',  'moi_approved',
        'duties_calculated', 'payment_confirmed',
    )
    def _compute_score(self):
        for r in self:
            checks = [
                r.acd_submitted, r.fasah_account_active,
                r.has_commercial_invoice, r.has_bill_of_lading,
                r.has_packing_list, r.has_coo,
                r.duties_calculated,
            ]
            if r.needs_saber:
                checks.append(r.saber_scoc_obtained)
            if r.needs_sfda:
                checks.append(r.sfda_approved)
            if r.needs_citc:
                checks.append(r.citc_approved)
            if r.needs_saso:
                checks.append(r.saso_approved)
            if r.needs_moi:
                checks.append(r.moi_approved)

            done  = sum(1 for c in checks if c)
            total = len(checks)
            r.compliance_score = int(done / total * 100) if total else 0

            missing = []
            if not r.acd_submitted:           missing.append('ACD not submitted')
            if not r.fasah_account_active:    missing.append('FASAH account not active')
            if not r.has_commercial_invoice:  missing.append('Commercial invoice missing')
            if not r.has_bill_of_lading:      missing.append('Bill of Lading missing')
            if not r.has_packing_list:        missing.append('Packing list missing')
            if not r.has_coo:                 missing.append('Certificate of Origin missing')
            if r.needs_saber and not r.saber_scoc_obtained: missing.append('SABER SCoC not obtained')
            if r.needs_sfda  and not r.sfda_approved:       missing.append('SFDA approval pending')
            if r.needs_citc  and not r.citc_approved:       missing.append('CITC certificate pending')
            if r.needs_saso  and not r.saso_approved:       missing.append('SASO certificate pending')
            if r.needs_moi   and not r.moi_approved:        missing.append('MoI permit pending')
            if not r.duties_calculated: missing.append('Duties not yet calculated')

            if missing:
                r.compliance_summary = 'Missing items:\n' + '\n'.join(f'  • {m}' for m in missing)
            else:
                r.compliance_summary = 'All compliance checks passed. Ready for submission.'

    def action_apply_to_clearance(self):
        self.ensure_one()
        cl = self.clearance_id
        vals = {
            'acd_reference_no':      self.acd_reference_no or cl.acd_reference_no,
            'fasah_declaration_no':  self.fasah_declaration_no or cl.fasah_declaration_no,
            'fatoorah_invoice_no':   self.fatoorah_invoice_no or cl.fatoorah_invoice_no,
            'saber_scoc_no':         self.saber_scoc_no or cl.saber_scoc_no,
            'saber_scoc_expiry':     self.saber_scoc_expiry or cl.saber_scoc_expiry,
            'saber_scoc_verified':   self.saber_scoc_obtained,
            'requires_sfda':         self.needs_sfda,
            'sfda_approval_no':      self.sfda_approval_no or cl.sfda_approval_no,
            'sfda_approved':         self.sfda_approved,
            'requires_citc':         self.needs_citc,
            'citc_certificate_no':   self.citc_certificate_no or cl.citc_certificate_no,
            'citc_approved':         self.citc_approved,
            'requires_saso':         self.needs_saso,
            'saso_certificate_no':   self.saso_certificate_no or cl.saso_certificate_no,
            'saso_approved':         self.saso_approved,
            'requires_moi':          self.needs_moi,
            'moi_permit_no':         self.moi_permit_no or cl.moi_permit_no,
            'moi_approved':          self.moi_approved,
            'sadad_payment_ref':     self.sadad_payment_ref or cl.sadad_payment_ref,
            'release_permit_no':     self.release_permit_no or cl.release_permit_no,
            'masar_tracking_no':     self.masar_tracking_no or cl.masar_tracking_no,
            'requires_saber':        self.needs_saber,
        }
        cl.write({k: v for k, v in vals.items() if v})
        return {'type': 'ir.actions.act_window_close'}
