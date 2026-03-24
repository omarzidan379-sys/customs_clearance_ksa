# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class CustomsDutyType(models.Model):
    _name = 'customs.duty.type'
    _description = 'Customs Duty Type'

    name = fields.Char(string='Duty/Tax Name', required=True, translate=True)
    code = fields.Char(string='Code')
    duty_category = fields.Selection([
        ('customs_duty', 'Customs Duty / رسوم جمركية'),
        ('vat', 'VAT / ضريبة قيمة مضافة'),
        ('excise', 'Excise Tax / ضريبة انتقائية'),
        ('service_fee', 'Service Fee / رسوم خدمة'),
        ('port_fee', 'Port Fee / رسوم ميناء'),
        ('other', 'Other / أخرى'),
    ], string='Category', default='customs_duty')
    default_rate = fields.Float(string='Default Rate (%)', digits=(5, 2))
    is_percentage = fields.Boolean(string='Percentage Based', default=True)
    active = fields.Boolean(default=True)


class CustomsDutyLine(models.Model):
    _name = 'customs.duty.line'
    _description = 'Customs Duty Line'

    clearance_id = fields.Many2one(
        'customs.clearance', string='Clearance Order',
        required=True, ondelete='cascade',
    )
    duty_type_id = fields.Many2one('customs.duty.type', string='Duty/Tax Type', required=True)
    duty_category = fields.Selection(related='duty_type_id.duty_category', store=True)
    base_amount = fields.Monetary(string='Base Amount', currency_field='currency_id')
    rate = fields.Float(string='Rate (%)', digits=(5, 2))
    amount = fields.Monetary(
        string='Amount',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(related='clearance_id.currency_id', store=True)
    is_percentage = fields.Boolean(related='duty_type_id.is_percentage', store=True)
    fixed_amount = fields.Monetary(string='Fixed Amount', currency_field='currency_id')
    payment_date = fields.Date(string='Payment Date')
    payment_reference = fields.Char(string='Payment Reference')
    notes = fields.Char(string='Notes')

    @api.depends('base_amount', 'rate', 'is_percentage', 'fixed_amount')
    def _compute_amount(self):
        for line in self:
            if line.is_percentage:
                line.amount = (line.base_amount or 0) * (line.rate or 0) / 100
            else:
                line.amount = line.fixed_amount or 0

    @api.onchange('duty_type_id')
    def _onchange_duty_type(self):
        if self.duty_type_id:
            self.rate = self.duty_type_id.default_rate
            self.is_percentage = self.duty_type_id.is_percentage
            # Auto-set base amount from CIF value
            if self.clearance_id:
                self.base_amount = self.clearance_id.cif_value
