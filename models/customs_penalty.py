# -*- coding: utf-8 -*-
"""
Customs Penalty & Appeal Management — غرامة جمركية واعتراض
============================================================
Covers all violation types defined in the Saudi Customs Law and
the ZATCA customs procedures rules.  Includes a formal appeal
workflow aligned with ZATCA's objection process.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class CustomsPenalty(models.Model):
    _name = 'customs.penalty'
    _description = 'Customs Penalty / Violation (غرامة جمركية)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'violation_date desc'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(readonly=True, default='New', copy=False, tracking=True)

    violation_type = fields.Selection([
        ('misdeclaration',   'Misdeclaration of Goods (إخفاء في البيان الجمركي)'),
        ('undervaluation',   'Goods Undervaluation (تخفيض قيمة البضاعة)'),
        ('prohibited',       'Prohibited Goods Import (بضاعة محظورة)'),
        ('missing_docs',     'Missing Required Documents (نقص في المستندات)'),
        ('late_acd',         'Late ACD Submission (تأخير بيان ACD)'),
        ('false_origin',     'False Certificate of Origin (شهادة منشأ مزورة)'),
        ('temp_overdue',     'Overdue Temporary Import (تجاوز مهلة الاستيراد المؤقت)'),
        ('country_marking',  'Country-of-Origin Marking Violation'),
        ('stowage',          'Bad Container Stowage'),
        ('demurrage_penalty','Customs Demurrage Penalty (غرامة إيواء)'),
        ('other',            'Other Violation'),
    ], string='Violation Type', required=True, tracking=True)

    state = fields.Selection([
        ('issued',   'Issued (صادرة)'),
        ('notified', 'Client Notified (تم الإخطار)'),
        ('paid',     'Paid (مدفوعة)'),
        ('appealed', 'Under Appeal (قيد الاعتراض)'),
        ('waived',   'Waived (معفاة)'),
        ('cancelled','Cancelled (ملغاة)'),
    ], default='issued', tracking=True, string='Status')

    # ── Links ─────────────────────────────────────────────────────────────────
    clearance_id      = fields.Many2one('customs.clearance', 'Related Clearance', ondelete='set null', tracking=True)
    partner_id        = fields.Many2one('res.partner', 'Violator / Party', required=True, tracking=True)
    customs_office_id = fields.Many2one('customs.port', 'Issuing Customs Office', domain=[('port_type', '=', 'customs_office')])
    company_id        = fields.Many2one('res.company', default=lambda s: s.env.company)

    # ── Financial ─────────────────────────────────────────────────────────────
    penalty_amount  = fields.Monetary('Penalty Amount (SAR)', required=True, tracking=True)
    currency_id     = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    final_amount    = fields.Monetary('Final Amount Due', compute='_compute_final_amount', store=True)

    # ── Dates ─────────────────────────────────────────────────────────────────
    violation_date = fields.Date('Violation Date', required=True, default=fields.Date.today)
    notice_date    = fields.Date('Notice Issued Date')
    due_date       = fields.Date('Payment Due Date', tracking=True)

    # ── References ────────────────────────────────────────────────────────────
    zatca_penalty_ref  = fields.Char('ZATCA / FASAH Penalty Ref.', tracking=True)
    violation_desc     = fields.Text('Violation Details', required=True)

    # ── Payment ───────────────────────────────────────────────────────────────
    payment_date      = fields.Date(tracking=True)
    payment_reference = fields.Char(tracking=True)
    sadad_reference   = fields.Char('SADAD Payment Ref.', tracking=True)

    # ── Appeal ────────────────────────────────────────────────────────────────
    appeal_date         = fields.Date(tracking=True)
    appeal_deadline     = fields.Date()
    appeal_reason       = fields.Text(tracking=True)
    appeal_submitted_by = fields.Many2one('res.users', 'Appeal Submitted By', tracking=True)
    appeal_decision     = fields.Selection([
        ('pending',  'Pending ZATCA Decision'),
        ('upheld',   'Upheld — Full Penalty'),
        ('reduced',  'Reduced — Partial Penalty'),
        ('dismissed','Dismissed — Penalty Waived'),
    ], tracking=True, string='Appeal Decision')
    appeal_decision_date = fields.Date('Decision Date', tracking=True)
    appeal_reduction_pct = fields.Float('Reduction (%)', default=50.0)
    appeal_notes         = fields.Text('Decision Notes')

    notes = fields.Text()

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends('penalty_amount', 'appeal_decision', 'appeal_reduction_pct')
    def _compute_final_amount(self):
        for rec in self:
            if rec.appeal_decision == 'dismissed':
                rec.final_amount = 0.0
            elif rec.appeal_decision == 'reduced':
                pct = max(0.0, min(100.0, rec.appeal_reduction_pct))
                rec.final_amount = rec.penalty_amount * (1 - pct / 100)
            else:
                rec.final_amount = rec.penalty_amount

    # ── Sequence ──────────────────────────────────────────────────────────────

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('customs.penalty') or 'PEN/NEW'
        return super().create(vals)

    # ── Workflow ──────────────────────────────────────────────────────────────

    def action_notify_client(self):
        self.write({'state': 'notified', 'notice_date': fields.Date.today()})
        self.message_post(body='Penalty notice sent to client.')

    def action_mark_paid(self):
        self.write({'state': 'paid', 'payment_date': fields.Date.today()})

    def action_submit_appeal(self):
        for rec in self:
            if not rec.appeal_reason:
                raise UserError('Provide an appeal reason before submitting to ZATCA.')
        self.write({
            'state':              'appealed',
            'appeal_date':        fields.Date.today(),
            'appeal_submitted_by': self.env.uid,
        })

    def action_enter_decision(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Enter Appeal Decision',
            'res_model': 'customs.penalty',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'flags': {'mode': 'edit'},
        }

    def action_waive(self):
        self.write({'state': 'waived'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
