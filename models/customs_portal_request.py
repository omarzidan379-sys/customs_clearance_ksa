# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CustomsPortalRequest(models.Model):
    """
    Shipment registration requests submitted by suppliers/customers
    via the external portal. A customs officer reviews, approves or
    rejects each request. On approval, a full clearance order is created.
    """
    _name = 'customs.portal.request'
    _description = 'Portal Shipment Registration Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'create_date desc'

    # ── Identification ────────────────────────────────────────────────────
    name = fields.Char(
        string='Request Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), tracking=True,
    )
    request_type = fields.Selection([
        ('supplier', 'Supplier / مورد'),
        ('customer', 'Customer / عميل'),
    ], string='Requester Type', required=True, default='supplier', tracking=True)

    state = fields.Selection([
        ('draft',    'Submitted / مقدم'),
        ('review',   'Under Review / قيد المراجعة'),
        ('approved', 'Approved / موافق عليه'),
        ('rejected', 'Rejected / مرفوض'),
    ], string='Status', default='draft', tracking=True, copy=False)

    priority = fields.Selection([
        ('0', 'Normal'), ('1', 'Urgent'), ('2', 'Very Urgent'),
    ], default='0', string='Priority')

    # ── Requester Info ────────────────────────────────────────────────────
    requester_name      = fields.Char(string='Full Name / الاسم الكامل',       required=True)
    requester_email     = fields.Char(string='Email / البريد الإلكتروني',       required=True)
    requester_phone     = fields.Char(string='Phone / رقم الجوال')
    requester_company   = fields.Char(string='Company Name / اسم الشركة',      required=True)
    requester_cr_no     = fields.Char(string='CR No. / السجل التجاري')
    requester_vat_no    = fields.Char(string='VAT No. / الرقم الضريبي')
    requester_country   = fields.Many2one('res.country', string='Country / الدولة')
    requester_city      = fields.Char(string='City / المدينة')

    # Partner link (set when/if partner exists in Odoo)
    partner_id = fields.Many2one('res.partner', string='Linked Partner', tracking=True)

    # ── Shipment Details ──────────────────────────────────────────────────
    clearance_type = fields.Selection([
        ('import',    'Import / استيراد'),
        ('export',    'Export / تصدير'),
        ('transit',   'Transit / ترانزيت'),
        ('temporary', 'Temporary Admission / قبول مؤقت'),
    ], string='Clearance Type', required=True, default='import', tracking=True)

    shipment_type = fields.Selection([
        ('sea',  'Sea Freight / شحن بحري'),
        ('air',  'Air Freight / شحن جوي'),
        ('road', 'Road Freight / شحن بري'),
    ], string='Shipment Type', default='sea', tracking=True)

    country_origin_id      = fields.Many2one('res.country', string='Country of Origin')
    country_destination_id = fields.Many2one('res.country', string='Country of Destination')
    port_of_loading        = fields.Char(string='Port of Loading / ميناء التحميل')
    port_of_discharge      = fields.Char(string='Port of Discharge / ميناء التفريغ')
    vessel_name            = fields.Char(string='Vessel / Carrier Name')
    bill_of_lading_no      = fields.Char(string='Bill of Lading No. / رقم بوليصة الشحن')
    eta                    = fields.Date(string='ETA / تاريخ الوصول المتوقع')
    gross_weight           = fields.Float(string='Gross Weight (kg)')
    volume                 = fields.Float(string='Volume (CBM)')
    packages_count         = fields.Integer(string='Number of Packages')

    # ── Goods Description ─────────────────────────────────────────────────
    goods_description  = fields.Text(string='Goods Description / وصف البضاعة', required=True)
    hs_codes_list      = fields.Text(string='HS Codes / الأرمزة الجمركية',
        help='Enter HS codes separated by commas e.g. 8471.30, 8517.12')
    estimated_value    = fields.Float(string='Estimated Goods Value (USD)')
    currency_note      = fields.Char(string='Currency', default='USD')

    # ── Documents Submitted ───────────────────────────────────────────────
    has_bill_of_lading = fields.Boolean(string='Bill of Lading attached')
    has_invoice        = fields.Boolean(string='Commercial Invoice attached')
    has_packing_list   = fields.Boolean(string='Packing List attached')
    has_coo            = fields.Boolean(string='Certificate of Origin attached')
    has_saber_scoc     = fields.Boolean(string='SABER SCoC attached')
    has_sfda           = fields.Boolean(string='SFDA Approval attached')
    has_citc           = fields.Boolean(string='CITC Certificate attached')
    additional_docs    = fields.Text(string='Additional Documents / مستندات إضافية')

    # ── Saudi References (if known) ───────────────────────────────────────
    acd_reference_no    = fields.Char(string='ACD Reference No. (if submitted)')
    saber_scoc_no       = fields.Char(string='SABER SCoC No.')
    sfda_approval_no    = fields.Char(string='SFDA Approval No.')
    fatoorah_invoice_no = fields.Char(string='FATOORAH Invoice No.')

    # ── Review & Decision ─────────────────────────────────────────────────
    reviewed_by      = fields.Many2one('res.users', string='Reviewed By', tracking=True)
    review_date      = fields.Datetime(string='Review Date', tracking=True)
    review_notes     = fields.Text(string='Review Notes / ملاحظات المراجع', tracking=True)
    rejection_reason = fields.Text(string='Rejection Reason / سبب الرفض', tracking=True)

    # ── Linked Clearance ──────────────────────────────────────────────────
    clearance_id = fields.Many2one(
        'customs.clearance', string='Created Clearance Order',
        readonly=True, tracking=True,
    )

    # ── Attachments ───────────────────────────────────────────────────────
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Attachments',
        relation='portal_request_attachment_rel',
    )
    attachment_count = fields.Integer(compute='_compute_attachment_count')

    # ── Submission metadata ───────────────────────────────────────────────
    submission_ip      = fields.Char(string='Submitted from IP')
    portal_token       = fields.Char(string='Portal Token', copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('customs.portal.token') or '')

    # ── Computes ──────────────────────────────────────────────────────────
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for r in self:
            r.attachment_count = len(r.attachment_ids)

    # ── ORM ──────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('customs.portal.request') or _('New')
        records = super().create(vals_list)
        for rec in records:
            rec._send_confirmation_email()
        return records

    # ── Workflow Actions ──────────────────────────────────────────────────
    def action_start_review(self):
        self.ensure_one()
        self.write({
            'state': 'review',
            'reviewed_by': self.env.user.id,
            'review_date': fields.Datetime.now(),
        })
        self.message_post(
            body=_('Request taken under review by %s.') % self.env.user.name,
        )

    def action_approve(self):
        """Approve the request and create a full Customs Clearance order."""
        self.ensure_one()
        if not self.review_notes:
            raise UserError(_('Please add review notes before approving.'))

        # Find or create partner
        partner = self.partner_id
        if not partner:
            country = self.requester_country
            partner = self.env['res.partner'].search(
                [('email', '=', self.requester_email)], limit=1
            )
            if not partner:
                partner = self.env['res.partner'].create({
                    'name':       self.requester_company or self.requester_name,
                    'email':      self.requester_email,
                    'phone':      self.requester_phone,
                    'vat':        self.requester_vat_no,
                    'company_type': 'company',
                    'country_id': country.id if country else False,
                    'city':       self.requester_city,
                })
            self.partner_id = partner

        # Create clearance order
        clearance_vals = {
            'clearance_type':    self.clearance_type,
            'partner_id':        partner.id,
            'date':              fields.Date.today(),
            'country_origin_id': self.country_origin_id.id if self.country_origin_id else False,
            'country_destination_id': self.country_destination_id.id if self.country_destination_id else False,
            'bill_of_lading_no': self.bill_of_lading_no,
            'description':       self.goods_description,
            'acd_reference_no':  self.acd_reference_no,
            'saber_scoc_no':     self.saber_scoc_no,
            'sfda_approval_no':  self.sfda_approval_no,
            'fatoorah_invoice_no': self.fatoorah_invoice_no,
            'requires_sfda':     bool(self.sfda_approval_no or self.has_sfda),
            'requires_saber':    bool(self.saber_scoc_no or self.has_saber_scoc),
            'requires_citc':     self.has_citc,
            'internal_notes':    '<p><b>Created from Portal Request:</b> %s</p><p>%s</p>' % (
                self.name, self.review_notes or ''
            ),
        }
        clearance = self.env['customs.clearance'].create(clearance_vals)

        self.write({
            'state':        'approved',
            'clearance_id': clearance.id,
        })
        self.message_post(
            body=_('Request APPROVED. Clearance order %s created.') % clearance.name,
        )
        self._send_decision_email('approved')
        return {
            'name': _('Clearance Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'customs.clearance',
            'view_mode': 'form',
            'res_id': clearance.id,
        }

    def action_reject(self):
        self.ensure_one()
        if not self.rejection_reason:
            raise UserError(_('Please enter a rejection reason before rejecting.'))
        self.write({'state': 'rejected'})
        self.message_post(
            body=_('Request REJECTED. Reason: %s') % self.rejection_reason,
        )
        self._send_decision_email('rejected')

    def action_reset_draft(self):
        self.ensure_one()
        self.write({'state': 'draft', 'rejection_reason': False})

    def action_view_clearance(self):
        self.ensure_one()
        return {
            'name': _('Clearance Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'customs.clearance',
            'view_mode': 'form',
            'res_id': self.clearance_id.id,
        }

    # ── Email Notifications ───────────────────────────────────────────────
    def _send_confirmation_email(self):
        """Send acknowledgement to the requester."""
        try:
            template = self.env.ref(
                'customs_clearance_ksa.email_template_portal_request_received',
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(self.id, force_send=True)
        except Exception:
            pass  # Don't block creation if email fails

    def _send_decision_email(self, decision):
        """Notify requester of approval or rejection."""
        try:
            tpl_key = 'customs_clearance_ksa.email_template_portal_request_%s' % decision
            template = self.env.ref(tpl_key, raise_if_not_found=False)
            if template:
                template.send_mail(self.id, force_send=True)
        except Exception:
            pass
