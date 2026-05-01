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

    # ── Offer / Contract ─────────────────────────────────────────────────
    estimated_service_fee = fields.Float(string='Estimated Service Fee (SAR)', default=0.0)
    estimated_duty_amount = fields.Float(string='Estimated Customs Duty (SAR)', default=0.0)
    offer_token    = fields.Char(string='Offer Token', copy=False, readonly=True)
    offer_state    = fields.Selection([
        ('none',     'Not Sent'),
        ('sent',     'Offer Sent'),
        ('accepted', 'Accepted by Customer'),
        ('rejected', 'Rejected by Customer'),
    ], string='Offer Status', default='none', tracking=True, copy=False)
    offer_sent_date    = fields.Datetime(string='Offer Sent Date', readonly=True)
    offer_replied_date = fields.Datetime(string='Customer Reply Date', readonly=True)

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
            rec._wa_send_new_request()
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

    def action_send_offer(self):
        """
        Send a service offer / mini-contract email to the customer.
        Creates a unique offer token they can use to accept or reject.
        """
        self.ensure_one()
        if not self.requester_email:
            raise UserError(_('No email address on file for this requester.'))

        if not self.offer_token:
            token = self.env['ir.sequence'].next_by_code('customs.portal.offer.token') or (
                'OFFER-%s' % self.id
            )
            self.offer_token = token

        vat_on_fee = round(self.estimated_service_fee * 0.15, 2)
        total_due  = round(self.estimated_service_fee + vat_on_fee + self.estimated_duty_amount, 2)
        base_url   = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        accept_url = '%s/customs-portal/offer/accept/%s' % (base_url, self.offer_token)
        reject_url = '%s/customs-portal/offer/reject/%s' % (base_url, self.offer_token)

        clearance_type_label = dict(self._fields['clearance_type'].selection).get(
            self.clearance_type, self.clearance_type
        )

        subject = _('Service Offer — Customs Clearance for %s') % self.requester_company
        body_html = """
<div style="font-family:Inter,-apple-system,sans-serif;max-width:620px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0">
  <div style="background:linear-gradient(135deg,#0a0f1e 0%%,#0369a1 100%%);padding:32px 28px;text-align:center">
    <h2 style="color:#ffffff;margin:0;font-size:22px;font-weight:700">Customs Clearance KSA</h2>
    <p style="color:rgba(255,255,255,0.7);margin:6px 0 0;font-size:13px">Service Offer &amp; Agreement — عرض خدمات</p>
  </div>

  <div style="padding:28px">
    <p style="color:#0f172a;font-size:15px;margin-bottom:4px">Dear <strong>%(name)s</strong>,</p>
    <p style="color:#334155;margin-top:0">
      Thank you for submitting your shipment registration request <strong>%(ref)s</strong>.
      We are pleased to present our service offer for your customs clearance.
    </p>

    <div style="background:#f0f9ff;border-left:4px solid #0ea5e9;border-radius:8px;padding:18px 20px;margin:20px 0">
      <h3 style="margin:0 0 12px;color:#0369a1;font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">
        Shipment Details — تفاصيل الشحنة
      </h3>
      <table style="width:100%%;border-collapse:collapse">
        <tr>
          <td style="padding:5px 0;color:#64748b;font-size:13px;width:45%%">Clearance Type</td>
          <td style="padding:5px 0;color:#0f172a;font-size:13px;font-weight:600">%(clearance_type)s</td>
        </tr>
        <tr>
          <td style="padding:5px 0;color:#64748b;font-size:13px">Goods</td>
          <td style="padding:5px 0;color:#0f172a;font-size:13px">%(goods)s</td>
        </tr>
        %(bl_row)s
      </table>
    </div>

    <div style="background:#f8fafc;border-radius:8px;padding:18px 20px;margin:20px 0">
      <h3 style="margin:0 0 12px;color:#0f172a;font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">
        Fee Breakdown — تفصيل الرسوم
      </h3>
      <table style="width:100%%;border-collapse:collapse">
        <tr>
          <td style="padding:6px 0;color:#64748b;font-size:13px;width:55%%">Clearance Service Fee</td>
          <td style="padding:6px 0;color:#0f172a;font-size:13px;text-align:right">SAR %(svc_fee).2f</td>
        </tr>
        <tr>
          <td style="padding:6px 0;color:#64748b;font-size:13px">VAT (15%% on service fee)</td>
          <td style="padding:6px 0;color:#0f172a;font-size:13px;text-align:right">SAR %(vat_fee).2f</td>
        </tr>
        %(duty_row)s
        <tr style="border-top:2px solid #cbd5e1">
          <td style="padding:10px 0;color:#0f172a;font-size:14px;font-weight:700">Total Estimated Amount</td>
          <td style="padding:10px 0;color:#0369a1;font-size:16px;font-weight:800;text-align:right">SAR %(total).2f</td>
        </tr>
      </table>
      <p style="color:#94a3b8;font-size:11px;margin:8px 0 0">
        * Customs duties are pass-through costs — exact amount depends on final assessment by ZATCA/Customs Authority.
        All amounts in Saudi Riyal (SAR) including 15%% VAT where applicable.
      </p>
    </div>

    <div style="background:#fef9c3;border-left:4px solid #f59e0b;border-radius:8px;padding:14px 18px;margin:20px 0">
      <p style="margin:0;color:#78350f;font-size:13px">
        <strong>Terms:</strong> Payment due within <strong>7 days</strong> of invoice issuance.
        SADAD payment available. Subject to final customs authority assessment.
      </p>
    </div>

    <p style="color:#334155;font-size:14px;font-weight:600;margin:24px 0 12px">
      Please confirm your acceptance of this offer:
    </p>

    <div style="text-align:center;margin:20px 0">
      <a href="%(accept_url)s"
         style="display:inline-block;padding:13px 32px;background:linear-gradient(135deg,#059669,#10b981);color:#ffffff;font-weight:700;font-size:14px;border-radius:10px;text-decoration:none;margin:0 8px">
        ✓ Accept Offer — قبول العرض
      </a>
      <a href="%(reject_url)s"
         style="display:inline-block;padding:13px 32px;background:#f1f5f9;color:#64748b;font-weight:600;font-size:14px;border-radius:10px;text-decoration:none;margin:0 8px;border:1px solid #cbd5e1">
        ✗ Decline — رفض
      </a>
    </div>

    <p style="color:#64748b;font-size:12px;margin-top:20px">
      If you have questions, reply to this email or call your assigned agent.
      This offer is valid for <strong>7 days</strong>.
    </p>
  </div>

  <div style="background:#f8fafc;padding:16px 28px;text-align:center;border-top:1px solid #e2e8f0">
    <p style="color:#94a3b8;font-size:11px;margin:0">
      Customs Clearance KSA — ZATCA · FASAH · SABER Compliant | Powered by Odoo 17
    </p>
  </div>
</div>""" % {
            'name':          self.requester_name,
            'ref':           self.name,
            'clearance_type': clearance_type_label,
            'goods':         (self.goods_description or '')[:80],
            'bl_row':        (
                '<tr><td style="padding:5px 0;color:#64748b;font-size:13px">BL No.</td>'
                '<td style="padding:5px 0;color:#0f172a;font-size:13px">%s</td></tr>' % self.bill_of_lading_no
            ) if self.bill_of_lading_no else '',
            'svc_fee':       self.estimated_service_fee,
            'vat_fee':       vat_on_fee,
            'duty_row':      (
                '<tr><td style="padding:6px 0;color:#64748b;font-size:13px">Estimated Customs Duty (pass-through)</td>'
                '<td style="padding:6px 0;color:#0f172a;font-size:13px;text-align:right">SAR %.2f</td></tr>' % self.estimated_duty_amount
            ) if self.estimated_duty_amount else '',
            'total':         total_due,
            'accept_url':    accept_url,
            'reject_url':    reject_url,
        }

        self.env['mail.mail'].sudo().create({
            'subject':    subject,
            'body_html':  body_html,
            'email_to':   self.requester_email,
            'auto_delete': True,
        }).send()

        self.write({
            'offer_state':     'sent',
            'offer_sent_date': fields.Datetime.now(),
        })
        self.message_post(
            body=_('Service offer sent to %s (%s). Awaiting customer response.')
                 % (self.requester_name, self.requester_email),
        )
        self._wa_send_offer()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title':   _('Offer Sent ✓'),
                'message': _('Service offer emailed to %s') % self.requester_email,
                'type':    'success',
                'sticky':  False,
            },
        }

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
        self._wa_send_approved()
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
        self._wa_send_rejected()

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

    def _get_tracking_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost')
        return '%s/customs-portal/tracking/%s' % (base_url, self.portal_token)

    def _ensure_portal_token(self):
        """Backfill any record that lost its portal_token."""
        if not self.portal_token:
            token = self.env['ir.sequence'].next_by_code('customs.portal.token') or (
                'CCK-%s' % self.env['ir.sequence']._next_sequence_code('customs.portal.token')
            )
            self.sudo().write({'portal_token': token})

    # ── Email Notifications ───────────────────────────────────────────────
    def _send_confirmation_email(self):
        """Send acknowledgement to the requester."""
        try:
            template = self.env.ref(
                'customs_clearance.email_template_portal_request_received',
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(self.id, force_send=True)
        except Exception:
            pass  # Don't block creation if email fails

    def _send_decision_email(self, decision):
        """Notify requester of approval or rejection."""
        try:
            tpl_key = 'customs_clearance.email_template_portal_request_%s' % decision
            template = self.env.ref(tpl_key, raise_if_not_found=False)
            if template:
                template.send_mail(self.id, force_send=True)
        except Exception:
            pass

    # ── WhatsApp Notifications ────────────────────────────────────────────

    def _wa(self):
        """Return the WhatsApp sender singleton."""
        return self.env['customs.whatsapp.sender']

    def _wa_send_new_request(self):
        sender = self._wa()
        if sender._wa_param('notify_new', '0') == '1':
            try:
                sender.send_to_admin(sender.msg_new_request(self))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning('WA new request: %s', e)

    def _wa_send_approved(self):
        sender = self._wa()
        if sender._wa_param('notify_approve', '0') == '1' and self.requester_phone:
            try:
                sender.send_whatsapp(self.requester_phone, sender.msg_approved(self))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning('WA approved: %s', e)

    def _wa_send_rejected(self):
        sender = self._wa()
        if sender._wa_param('notify_reject', '0') == '1' and self.requester_phone:
            try:
                sender.send_whatsapp(self.requester_phone, sender.msg_rejected(self))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning('WA rejected: %s', e)

    def _wa_send_offer(self):
        sender = self._wa()
        if sender._wa_param('notify_offer', '0') == '1' and self.requester_phone:
            try:
                sender.send_whatsapp(self.requester_phone, sender.msg_offer_sent(self))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning('WA offer: %s', e)
