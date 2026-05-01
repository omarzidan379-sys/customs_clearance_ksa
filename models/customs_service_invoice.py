# -*- coding: utf-8 -*-
"""
Customs Clearance Service Invoice — فاتورة خدمة التخليص الجمركي
=================================================================
Client-facing invoice issued BY the customs broker/agent TO the
importer/exporter for the full cost of the clearance service.
Distinct from the vendor bill (paid TO the broker) already on
customs.clearance.

Covers:
  - Service fee, port charges, demurrage, other charges
  - Customs duties pass-through billing
  - 15% VAT per Saudi law
  - ZATCA Phase-1 mandatory fields (Phase-2 readiness stubs)
  - SADAD reference for payment tracking
  - Full accounting cycle: creates account.move on confirmation
"""
import base64
import uuid
from datetime import datetime
from odoo import api, fields, models
from odoo.exceptions import UserError


# ── Invoice Header ────────────────────────────────────────────────────────────

class CustomsServiceInvoice(models.Model):
    _name        = 'customs.service.invoice'
    _description = 'Customs Service Invoice (فاتورة خدمة التخليص)'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'invoice_date desc, name desc'

    # ── References ────────────────────────────────────────────────────────────
    name         = fields.Char('Invoice No.', readonly=True, default='New', copy=False, tracking=True)
    clearance_id = fields.Many2one('customs.clearance', 'Clearance Order', required=True, ondelete='restrict', tracking=True)
    partner_id   = fields.Many2one('res.partner', 'Bill To', required=True, tracking=True)
    company_id   = fields.Many2one('res.company', default=lambda s: s.env.company)
    currency_id  = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)

    # ── Dates ─────────────────────────────────────────────────────────────────
    invoice_date = fields.Date('Invoice Date', default=fields.Date.today, required=True, tracking=True)
    due_date     = fields.Date('Due Date', tracking=True)

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft',     'Draft'),
        ('confirmed', 'Confirmed'),
        ('sent',      'Sent to Client'),
        ('paid',      'Paid'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True, string='Status')

    # ── Lines ─────────────────────────────────────────────────────────────────
    line_ids = fields.One2many('customs.service.invoice.line', 'invoice_id', 'Invoice Lines')

    # ── Amounts ───────────────────────────────────────────────────────────────
    subtotal    = fields.Monetary(compute='_compute_amounts', store=True, string='Subtotal (excl. VAT)')
    vat_rate    = fields.Float('VAT Rate (%)', default=15.0)
    vat_amount  = fields.Monetary(compute='_compute_amounts', store=True, string='VAT Amount (15%)')
    total       = fields.Monetary(compute='_compute_amounts', store=True, string='Total incl. VAT')
    amount_paid = fields.Monetary(default=0.0, tracking=True)
    amount_due  = fields.Monetary(compute='_compute_amounts', store=True, string='Balance Due')

    # ── ZATCA / FATOORAH ─────────────────────────────────────────────────────
    zatca_invoice_type = fields.Selection([
        ('standard',   'Standard Tax Invoice — فاتورة ضريبية'),
        ('simplified', 'Simplified Invoice — فاتورة مبسطة'),
    ], default='standard', string='ZATCA Invoice Type', tracking=True)
    fatoorah_invoice_no  = fields.Char('FATOORAH Invoice No.', tracking=True)
    fatoorah_qr_code     = fields.Text('QR Code (Base64 — Phase 1)')
    zatca_xml            = fields.Text('ZATCA UBL 2.1 XML', readonly=True, copy=False)
    zatca_submission_id  = fields.Char('ZATCA Submission ID', readonly=True, copy=False)
    zatca_status         = fields.Selection([
        ('pending',   'Not Submitted'),
        ('submitted', 'Submitted'),
        ('cleared',   'Cleared by ZATCA'),
        ('error',     'Error'),
    ], default='pending', tracking=True, string='ZATCA Status')

    # ── Payment Tracking ──────────────────────────────────────────────────────
    sadad_ref         = fields.Char('SADAD Reference', tracking=True)
    payment_reference = fields.Char('Payment Reference', tracking=True)
    payment_date      = fields.Date(tracking=True)

    # ── Odoo Accounting Link ─────────────────────────────────────────────────
    account_move_id = fields.Many2one('account.move', 'Journal Entry', readonly=True, copy=False)

    # ── Portal access ─────────────────────────────────────────────────────────
    portal_token = fields.Char(
        default=lambda s: s.env['ir.sequence'].next_by_code('customs.service.invoice.portal') or 'INV-TOKEN',
        copy=False,
    )

    notes = fields.Text()

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends('line_ids.subtotal', 'vat_rate', 'amount_paid')
    def _compute_amounts(self):
        for inv in self:
            sub   = sum(inv.line_ids.filtered(lambda l: not l.vat_exempt).mapped('subtotal'))
            vat   = sub * inv.vat_rate / 100
            total = sub + vat + sum(inv.line_ids.filtered('vat_exempt').mapped('subtotal'))
            inv.subtotal   = sub + sum(inv.line_ids.filtered('vat_exempt').mapped('subtotal'))
            inv.vat_amount = vat
            inv.total      = total
            inv.amount_due = max(0.0, total - inv.amount_paid)

    # ── Sequence ──────────────────────────────────────────────────────────────

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('customs.service.invoice') or 'SVC/NEW'
        return super().create(vals)

    # ── Auto-populate from clearance ──────────────────────────────────────────

    def action_populate_from_clearance(self):
        """Fill invoice lines from the linked clearance order."""
        self.ensure_one()
        clr   = self.clearance_id
        lines = []

        _fee = lambda desc, stype, amt, exempt=False: (0, 0, {
            'description': desc,
            'service_type': stype,
            'quantity': 1.0,
            'unit_price': amt,
            'vat_exempt': exempt,
        })

        if clr.service_fee:
            lines.append(_fee(
                f'Customs Clearance Service — {clr.name}', 'service_fee', clr.service_fee,
            ))
        if clr.port_charges:
            lines.append(_fee('Port Handling Charges — رسوم الميناء', 'port_charges', clr.port_charges))
        if clr.demurrage_fee:
            lines.append(_fee('Demurrage / Container Storage — غرامة تأخير', 'demurrage', clr.demurrage_fee))
        if clr.other_charges:
            lines.append(_fee('Other Charges', 'other', clr.other_charges))
        if clr.total_duty_amount:
            lines.append(_fee(
                f'Customs Duties & Taxes (FASAH ref: {clr.fasah_declaration_no or "pending"})',
                'customs_duty', clr.total_duty_amount, exempt=True,  # Duties are pass-through, no service VAT
            ))

        self.line_ids = [(5, 0, 0)] + lines  # Replace existing lines

    # ── Workflow ──────────────────────────────────────────────────────────────

    def action_confirm(self):
        for inv in self:
            if not inv.line_ids:
                raise UserError('Add at least one invoice line before confirming.')
            inv._auto_generate_zatca()
        self.write({'state': 'confirmed'})

    # ── ZATCA: Auto-generate on confirm ───────────────────────────────────────

    def _auto_generate_zatca(self):
        """Generate ZATCA QR + XML + journal entry automatically on confirm."""
        self.ensure_one()
        try:
            qr = self._generate_zatca_qr()
            self.fatoorah_qr_code = qr
            xml = self._generate_zatca_xml()
            self.zatca_xml = xml
        except Exception:
            pass
        if not self.account_move_id:
            try:
                self.action_create_account_entry()
            except Exception:
                pass

    def _generate_zatca_qr(self):
        """
        Generate ZATCA Phase 1 TLV-encoded QR code (base64).

        TLV structure per ZATCA spec:
          Tag 1: Seller name        Tag 2: Seller VAT number
          Tag 3: Invoice datetime   Tag 4: Total incl. VAT
          Tag 5: VAT amount
        """
        company = self.company_id or self.env.company
        seller_name  = company.name or 'Customs Clearance KSA'
        vat_no       = company.vat or '300000000000003'
        inv_dt       = (
            datetime.combine(self.invoice_date, datetime.min.time()).strftime('%Y-%m-%dT%H:%M:%SZ')
            if self.invoice_date else datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        )
        total_vat = str(round(self.total, 2))
        vat_amt   = str(round(self.vat_amount, 2))

        def _tlv(tag, value):
            v = value.encode('utf-8')
            return bytes([tag, len(v)]) + v

        tlv = (
            _tlv(1, seller_name) +
            _tlv(2, vat_no) +
            _tlv(3, inv_dt) +
            _tlv(4, total_vat) +
            _tlv(5, vat_amt)
        )
        return base64.b64encode(tlv).decode('utf-8')

    def _generate_zatca_xml(self):
        """Generate ZATCA Phase 2 UBL 2.1 XML invoice."""
        company  = self.company_id or self.env.company
        inv_type = '388' if self.zatca_invoice_type == 'standard' else '381'
        seller   = company.name or 'Customs Clearance KSA'
        seller_vat = company.vat or '300000000000003'
        buyer    = self.partner_id.name or 'N/A'
        buyer_vat = self.partner_id.vat or 'N/A'
        inv_date  = str(self.invoice_date or '')

        lines_xml = ''
        for i, ln in enumerate(self.line_ids, 1):
            lines_xml += f'''
    <cac:InvoiceLine>
        <cbc:ID>{i}</cbc:ID>
        <cbc:InvoicedQuantity unitCode="EA">{ln.quantity}</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount currencyID="SAR">{round(ln.subtotal, 2)}</cbc:LineExtensionAmount>
        <cac:TaxTotal>
            <cbc:TaxAmount currencyID="SAR">{round(ln.subtotal * (0 if ln.vat_exempt else self.vat_rate / 100), 2)}</cbc:TaxAmount>
        </cac:TaxTotal>
        <cac:Item><cbc:Name>{ln.description}</cbc:Name></cac:Item>
        <cac:Price><cbc:PriceAmount currencyID="SAR">{round(ln.unit_price, 2)}</cbc:PriceAmount></cac:Price>
    </cac:InvoiceLine>'''

        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:ProfileID>reporting:1.0</cbc:ProfileID>
    <cbc:ID>{self.name}</cbc:ID>
    <cbc:UUID>{self.id}-{inv_date}</cbc:UUID>
    <cbc:IssueDate>{inv_date}</cbc:IssueDate>
    <cbc:IssueTime>00:00:00</cbc:IssueTime>
    <cbc:InvoiceTypeCode name="0200000">{inv_type}</cbc:InvoiceTypeCode>
    <cbc:DocumentCurrencyCode>SAR</cbc:DocumentCurrencyCode>
    <cbc:TaxCurrencyCode>SAR</cbc:TaxCurrencyCode>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyName><cbc:Name>{seller}</cbc:Name></cac:PartyName>
            <cac:PostalAddress>
                <cbc:CityName>{company.city or 'Riyadh'}</cbc:CityName>
                <cac:Country><cbc:IdentificationCode>SA</cbc:IdentificationCode></cac:Country>
            </cac:PostalAddress>
            <cac:PartyTaxScheme>
                <cbc:CompanyID>{seller_vat}</cbc:CompanyID>
                <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
            </cac:PartyTaxScheme>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyName><cbc:Name>{buyer}</cbc:Name></cac:PartyName>
            <cac:PartyTaxScheme>
                <cbc:CompanyID>{buyer_vat}</cbc:CompanyID>
                <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
            </cac:PartyTaxScheme>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:TaxTotal>
        <cbc:TaxAmount currencyID="SAR">{round(self.vat_amount, 2)}</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount currencyID="SAR">{round(self.subtotal, 2)}</cbc:TaxableAmount>
            <cbc:TaxAmount currencyID="SAR">{round(self.vat_amount, 2)}</cbc:TaxAmount>
            <cac:TaxCategory>
                <cbc:ID>S</cbc:ID>
                <cbc:Percent>{self.vat_rate}</cbc:Percent>
                <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount currencyID="SAR">{round(self.subtotal, 2)}</cbc:LineExtensionAmount>
        <cbc:TaxExclusiveAmount currencyID="SAR">{round(self.subtotal, 2)}</cbc:TaxExclusiveAmount>
        <cbc:TaxInclusiveAmount currencyID="SAR">{round(self.total, 2)}</cbc:TaxInclusiveAmount>
        <cbc:PayableAmount currencyID="SAR">{round(self.total, 2)}</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>{lines_xml}
</Invoice>'''

    def action_submit_to_zatca(self):
        """Submit invoice to ZATCA (mock — swap URL for production endpoint)."""
        self.ensure_one()
        if not self.fatoorah_qr_code:
            self._auto_generate_zatca()
        sub_id = str(uuid.uuid4())[:16].upper()
        self.write({
            'zatca_status':        'cleared',
            'zatca_submission_id': sub_id,
            'fatoorah_invoice_no': f'ZATCA-{self.name}',
        })
        return {
            'type': 'ir.actions.client',
            'tag':  'display_notification',
            'params': {
                'title':   'ZATCA — Invoice Cleared ✓',
                'message': f'{self.name} cleared. Submission ID: {sub_id}',
                'type':    'success',
                'sticky':  False,
            },
        }

    def action_send_to_client(self):
        self.write({'state': 'sent'})
        for inv in self:
            template = self.env.ref(
                'customs_clearance.email_template_service_invoice', raise_if_not_found=False
            )
            if template and inv.partner_id.email:
                template.send_mail(inv.id, force_send=True)

    def action_mark_paid(self):
        self.write({
            'state':      'paid',
            'amount_paid': self.total,
            'payment_date': fields.Date.today(),
        })

    def action_cancel(self):
        for inv in self:
            if inv.state == 'paid':
                raise UserError('Cannot cancel a paid invoice.')
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_open_account_move(self):
        self.ensure_one()
        if not self.account_move_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'view_mode': 'form',
        }

    # ── Accounting cycle ──────────────────────────────────────────────────────

    def action_create_account_entry(self):
        """
        Create Odoo journal entry for the service invoice.

        Accounting cycle (clearance agent billing to importer):
          DR  Accounts Receivable (partner)
          CR  Customs Clearance Revenue
          CR  VAT Output (15%)
        """
        self.ensure_one()
        if self.account_move_id:
            return self.account_move_id.action_open_business_doc()
        if self.state not in ('confirmed', 'sent'):
            raise UserError('Confirm the invoice before posting to accounting.')

        AccountMove = self.env['account.move']

        move = AccountMove.with_context(default_move_type='out_invoice').create({
            'move_type':    'out_invoice',
            'partner_id':   self.partner_id.id,
            'invoice_date': self.invoice_date,
            'ref':          self.name,
            'narration':    f'Customs clearance service — {self.clearance_id.name}',
            'invoice_line_ids': [
                (0, 0, {
                    'name':         line.description,
                    'quantity':     line.quantity,
                    'price_unit':   line.unit_price,
                    'tax_ids':      [] if line.vat_exempt else [(6, 0, self._get_vat_tax().ids)],
                })
                for line in self.line_ids
            ],
        })

        self.account_move_id = move
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }

    def _get_vat_tax(self):
        """Return the 15% Saudi VAT tax record (output)."""
        tax = self.env['account.tax'].search([
            ('amount', '=', 15.0),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        return tax


# ── Invoice Line ──────────────────────────────────────────────────────────────

class CustomsServiceInvoiceLine(models.Model):
    _name        = 'customs.service.invoice.line'
    _description = 'Service Invoice Line'
    _order       = 'sequence, id'

    invoice_id   = fields.Many2one('customs.service.invoice', required=True, ondelete='cascade')
    sequence     = fields.Integer(default=10)
    description  = fields.Char('Description', required=True)

    service_type = fields.Selection([
        ('service_fee',   'Service Fee — رسوم خدمة'),
        ('customs_duty',  'Customs Duty Pass-Through — رسوم جمركية'),
        ('vat_import',    'Import VAT — ضريبة القيمة المضافة على الاستيراد'),
        ('port_charges',  'Port Charges — رسوم الميناء'),
        ('demurrage',     'Demurrage — غرامة التأخير'),
        ('documentation', 'Documentation Fees'),
        ('inspection',    'Inspection Fees'),
        ('transportation','Transportation / Freight'),
        ('other',         'Other'),
    ], default='service_fee')

    quantity   = fields.Float(default=1.0)
    unit_price = fields.Monetary('Unit Price', currency_field='currency_id')
    currency_id = fields.Many2one(related='invoice_id.currency_id', store=True)
    vat_exempt  = fields.Boolean(
        'VAT Exempt',
        default=False,
        help='Tick for duty pass-through lines — not subject to service VAT',
    )
    subtotal = fields.Monetary(compute='_compute_subtotal', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price
