# -*- coding: utf-8 -*-
"""
VIP / AEO Customer Management — عميل مميز / مشغّل اقتصادي معتمد
=================================================================
Manages the Saudi ZATCA "Awlawia" (أولويا) AEO programme and
internal VIP tiers. VIP profiles are linked 1-to-1 with res.partner
and automatically influence clearance priority, lane preference,
service-fee discounts, and dedicated broker assignment.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CustomsVipCustomer(models.Model):
    _name = 'customs.vip.customer'
    _description = 'VIP / AEO Customer Profile'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'vip_tier desc, partner_id'

    # ── Identity ──────────────────────────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True,
        ondelete='cascade', tracking=True,
    )
    display_name = fields.Char(compute='_compute_display_name', store=True)

    vip_tier = fields.Selection([
        ('silver',   'Silver — فضي'),
        ('gold',     'Gold — ذهبي'),
        ('platinum', 'Platinum — بلاتيني'),
        ('diamond',  'Diamond — ماسي'),
        ('aeo',      'AEO — مشغّل اقتصادي معتمد'),
    ], string='VIP Tier', required=True, default='silver', tracking=True)

    active = fields.Boolean(default=True)

    # ── AEO / ZATCA Fields ────────────────────────────────────────────────────
    aeo_certificate_no = fields.Char('AEO Certificate No.', tracking=True)
    aeo_issue_date     = fields.Date('AEO Issue Date')
    aeo_expiry_date    = fields.Date('AEO Expiry Date', tracking=True)
    aeo_expired        = fields.Boolean(compute='_compute_aeo_expired', store=True)
    zatca_importer_code = fields.Char('ZATCA Importer Code')
    gcc_aeo_recognized  = fields.Boolean('GCC Mutual AEO Recognition', default=False)

    # ── Service Benefits ──────────────────────────────────────────────────────
    service_fee_discount    = fields.Float('Service Fee Discount (%)', default=0.0)
    dedicated_broker_id     = fields.Many2one('customs.broker', 'Dedicated Broker')
    priority_processing     = fields.Boolean('Priority Processing', default=False, tracking=True)
    green_lane_preferred    = fields.Boolean('Prefer Green Lane', default=False)
    fast_track_inspection   = fields.Boolean('Fast-Track Inspection (Non-Intrusive)', default=False)

    # ── Credit Facility ───────────────────────────────────────────────────────
    credit_facility         = fields.Boolean('Credit Facility Enabled', default=False, tracking=True)
    credit_limit            = fields.Monetary('Credit Limit', currency_field='currency_id')
    duty_payment_days       = fields.Integer(
        'Duty Payment Postponement (days)', default=0,
        help='KSA allows up to 30-day postponement with guarantee',
    )
    currency_id             = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)

    # ── Statistics (read-only) ────────────────────────────────────────────────
    clearance_count         = fields.Integer(compute='_compute_stats', string='Clearances')
    total_service_fees      = fields.Monetary(compute='_compute_stats', string='Fees Paid (YTD)')
    avg_clearance_days      = fields.Float(compute='_compute_stats', string='Avg. Clearance Days')

    notes = fields.Text()

    _sql_constraints = [
        ('partner_unique', 'UNIQUE(partner_id)', 'This partner already has a VIP profile.'),
    ]

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends('partner_id', 'vip_tier')
    def _compute_display_name(self):
        tiers = dict(self._fields['vip_tier'].selection)
        for rec in self:
            tier = tiers.get(rec.vip_tier, '')
            rec.display_name = f'{rec.partner_id.name} [{tier}]' if rec.partner_id else ''

    @api.depends('aeo_expiry_date')
    def _compute_aeo_expired(self):
        today = fields.Date.today()
        for rec in self:
            rec.aeo_expired = bool(rec.aeo_expiry_date and rec.aeo_expiry_date < today)

    def _compute_stats(self):
        for rec in self:
            clearances = self.env['customs.clearance'].search([
                ('partner_id', '=', rec.partner_id.id),
                ('state', '!=', 'cancelled'),
            ])
            rec.clearance_count    = len(clearances)
            rec.total_service_fees = sum(clearances.mapped('service_fee'))

            done = clearances.filtered(
                lambda c: c.actual_clearance_date and c.date
            )
            if done:
                days = [(c.actual_clearance_date - c.date).days for c in done]
                rec.avg_clearance_days = sum(days) / len(days)
            else:
                rec.avg_clearance_days = 0.0

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_view_clearances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Clearances — {self.partner_id.name}',
            'res_model': 'customs.clearance',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': {'default_partner_id': self.partner_id.id},
        }

    @api.constrains('service_fee_discount')
    def _check_discount(self):
        for rec in self:
            if not (0 <= rec.service_fee_discount <= 100):
                raise ValidationError('Discount must be between 0% and 100%.')

    @api.constrains('duty_payment_days')
    def _check_duty_days(self):
        for rec in self:
            if rec.duty_payment_days > 30:
                raise ValidationError('KSA customs allows a maximum 30-day duty payment postponement.')
