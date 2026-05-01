# -*- coding: utf-8 -*-
"""
Customs Shipment Cost — تكاليف الشحنة الجمركية
================================================
Tracks all vendor costs linked to a customs clearance order:
  - Customs duties paid to authorities
  - Shipping line fees
  - Clearance service fees
  - Port charges, demurrage, transport, storage
  - Any other third-party costs

Each cost line can generate an Odoo vendor bill (account.move in_invoice).
The sum of confirmed costs vs. the service invoice revenue gives the
per-shipment profit/margin.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class CustomsShipmentCost(models.Model):
    _name        = 'customs.shipment.cost'
    _description = 'Shipment Cost — تكلفة الشحنة الجمركية'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'clearance_id, sequence, id'
    _rec_name    = 'name'

    # ── Identity ──────────────────────────────────────────────────────────────
    name         = fields.Char('Cost Description', required=True, tracking=True)
    sequence     = fields.Integer(default=10)
    clearance_id = fields.Many2one(
        'customs.clearance', string='Clearance Order',
        required=True, ondelete='cascade', tracking=True,
        index=True,
    )
    company_id   = fields.Many2one('res.company', default=lambda s: s.env.company)
    currency_id  = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)

    # ── Vendor ────────────────────────────────────────────────────────────────
    vendor_id = fields.Many2one(
        'res.partner', 'Vendor / Supplier', tracking=True,
        help='Customs authority, shipping line, or logistics provider',
    )

    # ── Cost type ─────────────────────────────────────────────────────────────
    cost_type = fields.Selection([
        ('customs_duty',   'Customs Duty — رسوم جمركية'),
        ('shipping',       'Shipping Line Fee — رسوم شحن'),
        ('clearance_fee',  'Clearance Service Fee — رسوم تخليص'),
        ('transport',      'Transportation — نقل'),
        ('port_charges',   'Port Charges — رسوم ميناء'),
        ('demurrage',      'Demurrage — غرامة تأخير'),
        ('inspection',     'Inspection Fee — رسوم فحص'),
        ('documentation',  'Documentation — مستندات'),
        ('storage',        'Storage / Warehouse — تخزين'),
        ('insurance',      'Insurance — تأمين'),
        ('vat_import',     'Import VAT — ضريبة استيراد'),
        ('other',          'Other — أخرى'),
    ], required=True, default='clearance_fee', tracking=True)

    # ── Amounts ───────────────────────────────────────────────────────────────
    amount      = fields.Monetary('Amount (excl. VAT)', required=True, tracking=True)
    vat_rate    = fields.Float('VAT %', default=15.0)
    vat_exempt  = fields.Boolean('VAT Exempt', default=False)
    vat_amount  = fields.Monetary(compute='_compute_total', store=True, string='VAT Amount')
    total_amount = fields.Monetary(compute='_compute_total', store=True, string='Total incl. VAT')

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft',     'Draft — مسودة'),
        ('confirmed', 'Confirmed — مؤكد'),
        ('billed',    'Vendor Bill Created — فاتورة مورد'),
        ('paid',      'Paid — مدفوع'),
    ], default='draft', tracking=True, string='Status')

    # ── Vendor Bill link ──────────────────────────────────────────────────────
    vendor_bill_id    = fields.Many2one('account.move', 'Vendor Bill', readonly=True, copy=False)
    bill_date         = fields.Date('Bill Date')
    payment_date      = fields.Date('Payment Date')
    payment_reference = fields.Char('Payment Reference')

    notes = fields.Text()

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends('amount', 'vat_rate', 'vat_exempt')
    def _compute_total(self):
        for cost in self:
            cost.vat_amount   = 0.0 if cost.vat_exempt else round(cost.amount * cost.vat_rate / 100, 2)
            cost.total_amount = cost.amount + cost.vat_amount

    # ── Workflow ──────────────────────────────────────────────────────────────

    def action_confirm(self):
        for cost in self:
            if cost.amount <= 0:
                raise UserError('Cost amount must be greater than zero.')
        self.write({'state': 'confirmed'})

    def action_create_vendor_bill(self):
        """Create Odoo vendor bill (in_invoice) from this cost line."""
        self.ensure_one()
        if self.vendor_bill_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': self.vendor_bill_id.id,
                'view_mode': 'form',
            }

        # Find purchase VAT tax
        tax_ids = []
        if not self.vat_exempt:
            tax = self.env['account.tax'].search([
                ('amount', '=', self.vat_rate),
                ('type_tax_use', '=', 'purchase'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if tax:
                tax_ids = [(6, 0, tax.ids)]

        journal = self.env['account.move'].with_context(
            default_move_type='in_invoice'
        )._get_default_journal()

        clr = self.clearance_id
        bill = self.env['account.move'].create({
            'move_type':    'in_invoice',
            'journal_id':   journal.id,
            'partner_id':   self.vendor_id.id if self.vendor_id else False,
            'invoice_date': fields.Date.today(),
            'ref':          f'{clr.name} — {self.get_cost_type_label()}',
            'narration': (
                f'Clearance: {clr.name} | '
                f'FASAH: {clr.fasah_declaration_no or "N/A"} | '
                f'Cost type: {self.get_cost_type_label()}'
            ),
            'invoice_line_ids': [(0, 0, {
                'name':       self.name,
                'quantity':   1.0,
                'price_unit': self.amount,
                'tax_ids':    tax_ids,
            })],
        })

        self.write({
            'vendor_bill_id': bill.id,
            'state':          'billed',
            'bill_date':      fields.Date.today(),
        })
        return {
            'type':      'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id':    bill.id,
            'view_mode': 'form',
            'target':    'current',
        }

    def action_mark_paid(self):
        self.write({'state': 'paid', 'payment_date': fields.Date.today()})

    def action_reset_draft(self):
        self.filtered(lambda c: c.state == 'confirmed').write({'state': 'draft'})

    def get_cost_type_label(self):
        self.ensure_one()
        return dict(self._fields['cost_type'].selection).get(self.cost_type, self.cost_type)
