# -*- coding: utf-8 -*-
"""
Customs Bond / Guarantee Management — كفالة جمركية
====================================================
Tracks the three KSA customs guarantee types (cash, bank, documentary)
as well as AEO global guarantees and transit bonds.  Each bond can be
linked to a clearance order and carries a full state machine from
issuance through release or forfeiture.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class CustomsBond(models.Model):
    _name = 'customs.bond'
    _description = 'Customs Bond / Guarantee (كفالة جمركية)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'issue_date desc'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        'Bond Reference', readonly=True, default='New', copy=False, tracking=True,
    )
    bond_type = fields.Selection([
        ('cash_guarantee',   'Cash Guarantee (ضمان نقدي)'),
        ('bank_guarantee',   'Bank Letter of Guarantee (ضمان بنكي)'),
        ('documentary',      'Documentary Guarantee (ضمان وثائقي)'),
        ('temporary_import', 'Temporary Import Bond (استيراد مؤقت)'),
        ('temporary_export', 'Temporary Export Bond'),
        ('transit',          'Transit Bond (كفالة عبور)'),
        ('aeo_global',       'AEO Global Guarantee'),
    ], string='Bond Type', required=True, default='bank_guarantee', tracking=True)

    state = fields.Selection([
        ('draft',              'Draft'),
        ('active',             'Active (نشط)'),
        ('partially_released', 'Partially Released'),
        ('released',           'Released (محرَّر)'),
        ('forfeited',          'Forfeited (مصادَر)'),
        ('expired',            'Expired (منتهي)'),
    ], default='draft', tracking=True, string='Status')

    # ── Parties ───────────────────────────────────────────────────────────────
    partner_id        = fields.Many2one('res.partner', 'Importer / Exporter', required=True, tracking=True)
    guarantor_id      = fields.Many2one('res.partner', 'Bank / Guarantor', tracking=True)
    clearance_id      = fields.Many2one('customs.clearance', 'Related Clearance', ondelete='set null', tracking=True)
    customs_office_id = fields.Many2one(
        'customs.port', 'Issuing Customs Office',
        domain=[('port_type', '=', 'customs_office')],
    )
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

    # ── Financial ─────────────────────────────────────────────────────────────
    bond_amount      = fields.Monetary('Bond Amount', tracking=True)
    currency_id      = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    bond_reference   = fields.Char('Bond Reference No.', tracking=True)
    sadad_ref        = fields.Char('SADAD Reference')

    # ── Dates ─────────────────────────────────────────────────────────────────
    issue_date     = fields.Date('Issue Date',  default=fields.Date.today, tracking=True)
    expiry_date    = fields.Date('Expiry Date', tracking=True)
    is_expired     = fields.Boolean(compute='_compute_expired', store=True)
    days_to_expiry = fields.Integer(compute='_compute_expired', store=True)

    # ── Release ───────────────────────────────────────────────────────────────
    release_date      = fields.Date('Release Date', tracking=True)
    release_reference = fields.Char('Release Reference', tracking=True)
    released_amount   = fields.Monetary('Released Amount')
    forfeiture_reason = fields.Text('Forfeiture Reason')

    # ── Content ───────────────────────────────────────────────────────────────
    goods_description = fields.Text('Bonded Goods Description')
    conditions        = fields.Text('Bond Conditions')
    notes             = fields.Text()

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends('expiry_date')
    def _compute_expired(self):
        today = fields.Date.today()
        for rec in self:
            if rec.expiry_date:
                delta = (rec.expiry_date - today).days
                rec.days_to_expiry = delta
                rec.is_expired     = delta < 0
            else:
                rec.days_to_expiry = 0
                rec.is_expired     = False

    # ── Sequence ──────────────────────────────────────────────────────────────

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('customs.bond') or 'BOND/NEW'
        return super().create(vals)

    # ── Workflow ──────────────────────────────────────────────────────────────

    def action_activate(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Only Draft bonds can be activated.')
        self.write({'state': 'active'})

    def action_release(self):
        self.write({'state': 'released', 'release_date': fields.Date.today()})

    def action_forfeit(self):
        for rec in self:
            if not rec.forfeiture_reason:
                raise UserError('Please enter a forfeiture reason.')
        self.write({'state': 'forfeited'})

    def action_expire(self):
        self.write({'state': 'expired'})
