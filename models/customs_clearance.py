# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date


class CustomsClearance(models.Model):
    _name = 'customs.clearance'
    _description = 'Customs Clearance Order — Saudi KSA'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc, id desc'

    # ── Identification ────────────────────────────────────────────────────────
    name = fields.Char(string='Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), tracking=True)
    clearance_type = fields.Selection([
        ('import',    'Import / استيراد'),
        ('export',    'Export / تصدير'),
        ('transit',   'Transit / ترانزيت'),
        ('temporary', 'Temporary Admission / قبول مؤقت'),
    ], string='Clearance Type', required=True, default='import', tracking=True)

    state = fields.Selection([
        ('draft',          'Draft / مسودة'),
        ('acd_submitted',  'ACD Submitted / تم تقديم ACD'),
        ('submitted',      'Submitted to FASAH / مقدمة في فسح'),
        ('customs_review', 'Customs Review / مراجعة جمركية'),
        ('inspection',     'Under Inspection / تحت الفحص'),
        ('duty_payment',   'Duty Payment / سداد الرسوم'),
        ('released',       'Released / إذن الإفراج'),
        ('delivered',      'Delivered / مُسلَّم'),
        ('cancelled',      'Cancelled / ملغي'),
    ], string='Status', default='draft', tracking=True, copy=False)

    inspection_lane = fields.Selection([
        ('green',  'Green Lane / الممر الأخضر'),
        ('yellow', 'Yellow Lane / الممر الأصفر'),
        ('red',    'Red Lane / الممر الأحمر'),
    ], string='Inspection Lane / مسار الشحنة', tracking=True)

    priority = fields.Selection([
        ('0', 'Normal'), ('1', 'Urgent'), ('2', 'Very Urgent'),
    ], string='Priority', default='0')

    # ── Dates ─────────────────────────────────────────────────────────────────
    date = fields.Date(string='Date', default=fields.Date.today, required=True, tracking=True)
    expected_clearance_date  = fields.Date(string='Expected Clearance Date', tracking=True)
    actual_clearance_date    = fields.Date(string='Actual Clearance Date',   tracking=True)
    customs_declaration_date = fields.Date(string='Declaration Date',        tracking=True)
    acd_submission_date      = fields.Date(string='ACD Submission Date',     tracking=True)
    release_date             = fields.Date(string='Release Date',            tracking=True)

    # ── Parties ───────────────────────────────────────────────────────────────
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', string='Importer/Exporter',
        required=True, tracking=True)
    broker_id = fields.Many2one('customs.broker', string='Customs Broker / المخلص الجمركي',
        tracking=True)
    broker_license_no = fields.Char(string='Broker License No.',
        related='broker_id.license_number', store=True)
    is_aeo = fields.Boolean(string='AEO Importer / مشغل اقتصادي معتمد', tracking=True)
    aeo_certificate_no = fields.Char(string='AEO Certificate No. / رقم شهادة AEO', tracking=True)

    # ── Port & Customs ────────────────────────────────────────────────────────
    port_id = fields.Many2one('customs.port', string='Port of Entry/Exit', tracking=True)
    customs_office_id = fields.Many2one('customs.port', string='Customs Office',
        domain=[('port_type', '=', 'customs_office')], tracking=True)
    country_origin_id      = fields.Many2one('res.country', string='Country of Origin', tracking=True)
    country_destination_id = fields.Many2one('res.country', string='Country of Destination', tracking=True)

    # ── General Reference Numbers ─────────────────────────────────────────────
    customs_declaration_no = fields.Char(string='Customs Declaration No. / رقم البيان الجمركي',
        tracking=True, copy=False)
    bill_of_lading_no = fields.Char(string='Bill of Lading No. / رقم بوليصة الشحن', tracking=True)
    airway_bill_no    = fields.Char(string='Airway Bill No.',  tracking=True)
    shipment_id       = fields.Many2one('customs.shipment', string='Shipment', tracking=True)
    purchase_order_id = fields.Many2one('purchase.order',   string='Purchase Order', tracking=True)
    invoice_id        = fields.Many2one('account.move',     string='Commercial Invoice', tracking=True)

    # ── Saudi-Specific Reference Numbers ─────────────────────────────────────
    fasah_declaration_no = fields.Char(
        string='FASAH Declaration No. / رقم البيان في فسح',
        tracking=True, copy=False,
        help='Official FASAH system reference for the electronic declaration.')
    acd_reference_no = fields.Char(
        string='ACD Reference No. / رقم مرجع ACD',
        tracking=True, copy=False,
        help='Advance Cargo Declaration reference — submit 24h before departure.')
    fatoorah_invoice_no = fields.Char(
        string='FATOORAH Invoice No. / رقم الفاتورة الإلكترونية',
        tracking=True,
        help='ZATCA Phase 2 e-invoice reference (FATOORAH compliance).')
    sadad_payment_ref = fields.Char(
        string='SADAD Payment Ref. / مرجع سداد',
        tracking=True,
        help='Payment confirmation number from SADAD / Fasah Pay.')
    release_permit_no = fields.Char(
        string='Release Permit No. / رقم إذن الإفراج',
        tracking=True, copy=False,
        help='Electronic release permit issued by FASAH customs.')
    masar_tracking_no = fields.Char(
        string='MASAR Tracking No. / رقم تتبع مسار',
        tracking=True,
        help='Real-time delivery tracking from the MASAR system.')

    # ── SABER Certificates ────────────────────────────────────────────────────
    requires_saber     = fields.Boolean(string='Requires SABER / يستلزم سابر')
    saber_pcoc_no      = fields.Char(string='SABER PCoC No. / رقم شهادة مطابقة المنتج', tracking=True)
    saber_scoc_no      = fields.Char(string='SABER SCoC No. / رقم شهادة مطابقة الشحنة', tracking=True)
    saber_scoc_expiry  = fields.Date(string='SCoC Expiry Date / تاريخ انتهاء SCoC', tracking=True)
    saber_scoc_verified= fields.Boolean(string='SCoC Verified in FASAH / محقق في فسح', tracking=True)

    # ── Regulatory Compliance Flags ───────────────────────────────────────────
    requires_sfda       = fields.Boolean(string='Requires SFDA Approval')
    sfda_approval_no    = fields.Char(string='SFDA Approval No.',  tracking=True)
    sfda_approved       = fields.Boolean(string='SFDA Approved',   tracking=True)

    requires_citc       = fields.Boolean(string='Requires CITC Certificate')
    citc_certificate_no = fields.Char(string='CITC Certificate No.', tracking=True)
    citc_approved       = fields.Boolean(string='CITC Approved',     tracking=True)

    requires_saso       = fields.Boolean(string='Requires SASO')
    saso_certificate_no = fields.Char(string='SASO Certificate No.', tracking=True)
    saso_approved       = fields.Boolean(string='SASO Approved',     tracking=True)

    requires_moi        = fields.Boolean(string='Requires MoI Permit')
    moi_permit_no       = fields.Char(string='MoI Permit No.',       tracking=True)
    moi_approved        = fields.Boolean(string='MoI Approved',      tracking=True)

    compliance_status = fields.Selection([
        ('pending',   'Pending / معلق'),
        ('partial',   'Partial / جزئي'),
        ('compliant', 'Compliant / ممتثل'),
        ('violation', 'Violation / مخالفة'),
    ], string='Compliance Status', compute='_compute_compliance_status', store=True)

    # ── Goods ────────────────────────────────────────────────────────────────
    description    = fields.Text(string='Goods Description / وصف البضاعة')
    goods_line_ids = fields.One2many('customs.clearance.line', 'clearance_id', string='Goods Lines')

    # ── Financial ─────────────────────────────────────────────────────────────
    currency_id = fields.Many2one('res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    goods_value      = fields.Monetary(string='Goods Value (FOB)', currency_field='currency_id', tracking=True)
    freight_amount   = fields.Monetary(string='Freight Amount',    currency_field='currency_id')
    insurance_amount = fields.Monetary(string='Insurance Amount',  currency_field='currency_id')
    cif_value        = fields.Monetary(string='CIF Value',
        compute='_compute_cif_value', store=True, currency_field='currency_id')
    duty_line_ids    = fields.One2many('customs.duty.line', 'clearance_id', string='Duties & Taxes')
    total_duty_amount= fields.Monetary(string='Total Duties & Taxes',
        compute='_compute_totals', store=True, currency_field='currency_id')
    service_fee      = fields.Monetary(string='Broker Service Fee', currency_field='currency_id', tracking=True)
    port_charges     = fields.Monetary(string='Port Charges / رسوم الميناء',  currency_field='currency_id')
    demurrage_fee    = fields.Monetary(string='Demurrage Fee / رسوم الوقوف',   currency_field='currency_id')
    other_charges    = fields.Monetary(string='Other Charges',                 currency_field='currency_id')
    total_cost       = fields.Monetary(string='Total Cost',
        compute='_compute_totals', store=True, currency_field='currency_id')
    payment_status   = fields.Selection([
        ('unpaid',   'Unpaid / غير مسدد'),
        ('partial',  'Partial / جزئي'),
        ('paid',     'Paid / مسدد'),
        ('deferred', 'Deferred AEO / مؤجل'),
    ], string='Payment Status', default='unpaid', tracking=True)

    # ── Documents ─────────────────────────────────────────────────────────────
    document_ids   = fields.One2many('customs.document', 'clearance_id', string='Documents')
    document_count = fields.Integer(compute='_compute_document_count')

    # ── Notes ────────────────────────────────────────────────────────────────
    internal_notes = fields.Html(string='Internal Notes')
    customs_notes  = fields.Text(string='Customs Office Notes')
    zatca_remarks  = fields.Text(string='ZATCA Remarks / ملاحظات ZATCA')
    color          = fields.Integer(string='Color')

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends('goods_value', 'freight_amount', 'insurance_amount')
    def _compute_cif_value(self):
        for r in self:
            r.cif_value = (r.goods_value or 0) + (r.freight_amount or 0) + (r.insurance_amount or 0)

    @api.depends('duty_line_ids.amount', 'service_fee', 'port_charges', 'demurrage_fee', 'other_charges', 'cif_value')
    def _compute_totals(self):
        for r in self:
            r.total_duty_amount = sum(r.duty_line_ids.mapped('amount'))
            r.total_cost = r.cif_value + r.total_duty_amount + (r.service_fee or 0) + (r.port_charges or 0) + (r.demurrage_fee or 0) + (r.other_charges or 0)

    @api.depends('document_ids')
    def _compute_document_count(self):
        for r in self:
            r.document_count = len(r.document_ids)

    @api.depends('requires_sfda', 'sfda_approved', 'requires_citc', 'citc_approved',
                 'requires_saso', 'saso_approved', 'requires_moi', 'moi_approved',
                 'acd_reference_no', 'fasah_declaration_no')
    def _compute_compliance_status(self):
        for r in self:
            pairs = [
                (r.requires_sfda, r.sfda_approved),
                (r.requires_citc, r.citc_approved),
                (r.requires_saso, r.saso_approved),
                (r.requires_moi,  r.moi_approved),
            ]
            required  = [p for p in pairs if p[0]]
            compliant = [p for p in required if p[1]]
            if not required:
                r.compliance_status = 'compliant' if (r.acd_reference_no and r.fasah_declaration_no) else 'partial' if (r.acd_reference_no or r.fasah_declaration_no) else 'pending'
            elif len(compliant) == len(required):
                r.compliance_status = 'compliant'
            elif compliant:
                r.compliance_status = 'partial'
            else:
                r.compliance_status = 'pending'

    # ── ORM ──────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                ct = vals.get('clearance_type', 'import')
                vals['name'] = self.env['ir.sequence'].next_by_code(f'customs.clearance.{ct}') or _('New')
        return super().create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        default.update({'name': _('New'), 'state': 'draft',
            'customs_declaration_no': False, 'fasah_declaration_no': False,
            'acd_reference_no': False, 'release_permit_no': False,
            'sadad_payment_ref': False, 'actual_clearance_date': False})
        return super().copy(default)

    # ── Workflow ──────────────────────────────────────────────────────────────
    def action_submit_acd(self):
        self.ensure_one()
        if not self.acd_reference_no:
            raise UserError(_('Enter the ACD Reference Number. The Advance Cargo Declaration must be submitted to ZATCA at least 24 hours before cargo departure.'))
        self.write({'state': 'acd_submitted', 'acd_submission_date': fields.Date.today()})

    def action_submit_fasah(self):
        self.ensure_one()
        if not self.goods_line_ids:
            raise UserError(_('Add at least one goods line before submitting.'))
        if self.requires_saber and not self.saber_scoc_no:
            raise UserError(_('SABER SCoC certificate number is required for this shipment.'))
        self.write({'state': 'submitted'})

    def action_customs_review(self):
        self.ensure_one()
        self.write({'state': 'customs_review'})

    def action_green_lane(self):
        self.ensure_one()
        self.write({'state': 'duty_payment', 'inspection_lane': 'green'})
        self.message_post(body=_('Green Lane assigned — proceeding to duty payment.'))

    def action_yellow_lane(self):
        self.ensure_one()
        self.write({'state': 'customs_review', 'inspection_lane': 'yellow'})
        self.message_post(body=_('Yellow Lane assigned — document verification required (1–2 working days).'))

    def action_red_lane(self):
        self.ensure_one()
        self.write({'state': 'inspection', 'inspection_lane': 'red'})
        self.message_post(body=_('Red Lane assigned — full physical inspection required (3–5 working days).'))

    def action_inspection(self):
        self.ensure_one()
        self.write({'state': 'inspection'})

    def action_duty_payment(self):
        self.ensure_one()
        self.write({'state': 'duty_payment'})

    def action_release(self):
        self.ensure_one()
        if not self.release_permit_no:
            raise UserError(_('Enter the Electronic Release Permit No. (إذن الإفراج) issued by FASAH.'))
        self.write({'state': 'released', 'actual_clearance_date': fields.Date.today(),
                    'release_date': fields.Date.today(), 'payment_status': 'paid'})

    def action_deliver(self):
        self.ensure_one()
        self.write({'state': 'delivered'})

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'delivered':
            raise UserError(_('Cannot cancel a delivered order.'))
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.ensure_one()
        self.write({'state': 'draft'})

    def action_view_documents(self):
        self.ensure_one()
        return {'name': _('Documents'), 'type': 'ir.actions.act_window',
                'res_model': 'customs.document', 'view_mode': 'list,form',
                'domain': [('clearance_id', '=', self.id)],
                'context': {'default_clearance_id': self.id}}

    def action_open_compliance_wizard(self):
        self.ensure_one()
        return {'name': _('Saudi Compliance Checklist'), 'type': 'ir.actions.act_window',
                'res_model': 'customs.compliance.wizard', 'view_mode': 'form',
                'target': 'new', 'context': {'default_clearance_id': self.id}}

    def action_create_vendor_bill(self):
        self.ensure_one()
        if not self.broker_id or not self.broker_id.partner_id:
            raise UserError(_('Please set a customs broker before creating a bill.'))
        lines = []
        if self.service_fee:
            lines.append((0, 0, {'name': _('Broker Service Fee — %s') % self.name, 'quantity': 1, 'price_unit': self.service_fee}))
        for d in self.duty_line_ids:
            lines.append((0, 0, {'name': '%s — %s' % (d.duty_type_id.name, self.name), 'quantity': 1, 'price_unit': d.amount}))
        if self.port_charges:
            lines.append((0, 0, {'name': _('Port Charges — %s') % self.name, 'quantity': 1, 'price_unit': self.port_charges}))
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.broker_id.partner_id.id,
            'invoice_date': fields.Date.today(), 'invoice_line_ids': lines, 'ref': self.name,
            'narration': 'SADAD: %s | FASAH: %s' % (self.sadad_payment_ref or '—', self.fasah_declaration_no or '—'),
        })
        return {'name': _('Vendor Bill'), 'type': 'ir.actions.act_window',
                'res_model': 'account.move', 'view_mode': 'form', 'res_id': bill.id}

    @api.constrains('expected_clearance_date', 'date')
    def _check_dates(self):
        for r in self:
            if r.expected_clearance_date and r.date and r.expected_clearance_date < r.date:
                raise ValidationError(_('Expected Clearance Date cannot be before the order date.'))

    @api.constrains('saber_scoc_expiry')
    def _check_saber_expiry(self):
        for r in self:
            if r.saber_scoc_expiry and r.saber_scoc_expiry < date.today():
                raise ValidationError(_('SABER SCoC certificate expired on %s. Obtain a new certificate from SABER.') % r.saber_scoc_expiry)

    @api.onchange('is_aeo')
    def _onchange_is_aeo(self):
        if self.is_aeo:
            self.inspection_lane = 'green'


class CustomsClearanceLine(models.Model):
    _name = 'customs.clearance.line'
    _description = 'Customs Clearance Goods Line'

    clearance_id      = fields.Many2one('customs.clearance', required=True, ondelete='cascade')
    sequence          = fields.Integer(default=10)
    product_id        = fields.Many2one('product.product', string='Product')
    description       = fields.Char(string='Description / الوصف', required=True)
    hs_code_id        = fields.Many2one('customs.hs.code', string='HS Code / الرمز الجمركي')
    hs_code           = fields.Char(related='hs_code_id.code', store=True)
    country_origin_id = fields.Many2one('res.country', string='Country of Origin')
    quantity          = fields.Float(string='Quantity', digits='Product Unit of Measure', default=1.0)
    uom_id            = fields.Many2one('uom.uom', string='UoM')
    unit_weight       = fields.Float(string='Unit Weight (kg)')
    total_weight      = fields.Float(string='Total Weight (kg)', compute='_compute_total_weight', store=True)
    unit_value        = fields.Monetary(string='Unit Value',  currency_field='currency_id')
    total_value       = fields.Monetary(string='Total Value', compute='_compute_total_value', store=True, currency_field='currency_id')
    currency_id       = fields.Many2one(related='clearance_id.currency_id', store=True)
    saudi_import_duty_rate = fields.Float(string='KSA Duty Rate (%)', related='hs_code_id.import_duty_rate', store=True)
    saudi_vat_rate    = fields.Float(string='VAT Rate (%)', digits=(5,2), default=15.0)
    excise_rate       = fields.Float(string='Excise Rate (%)', digits=(5,2), default=0.0)
    requires_saber    = fields.Boolean(string='SABER Required', related='hs_code_id.requires_saber', store=True)
    requires_sfda     = fields.Boolean(string='SFDA Required',  related='hs_code_id.requires_sfda',  store=True)
    requires_citc     = fields.Boolean(string='CITC Required',  related='hs_code_id.requires_citc',  store=True)
    notes             = fields.Char(string='Notes')

    @api.depends('quantity', 'unit_weight')
    def _compute_total_weight(self):
        for l in self:
            l.total_weight = l.quantity * l.unit_weight

    @api.depends('quantity', 'unit_value')
    def _compute_total_value(self):
        for l in self:
            l.total_value = l.quantity * l.unit_value
