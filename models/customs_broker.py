# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date

class CustomsBroker(models.Model):
    _name = 'customs.broker'
    _description = 'Customs Broker / مخلص جمركي'
    _inherit = ['mail.thread']
    _rec_name = 'name'

    name            = fields.Char(string='Broker Name', required=True, tracking=True)
    partner_id      = fields.Many2one('res.partner', string='Related Contact', required=True)
    license_number  = fields.Char(string='License Number / رقم الترخيص', required=True, tracking=True)
    license_expiry_date = fields.Date(string='License Expiry Date', tracking=True)
    license_expired = fields.Boolean(string='License Expired', compute='_compute_license_expired', store=True)

    # Saudi-specific
    zatca_broker_code = fields.Char(string='ZATCA Broker Code / رمز المخلص في ZATCA', tracking=True)
    fasah_username    = fields.Char(string='FASAH Username', tracking=True)
    is_aeo_broker     = fields.Boolean(string='AEO Certified Broker', tracking=True)
    aeo_cert_no       = fields.Char(string='AEO Certificate No.', tracking=True)

    customs_office_ids = fields.Many2many('customs.port', string='Authorized Customs Offices',
        domain=[('port_type', '=', 'customs_office')])
    specialization = fields.Selection([
        ('import', 'Import'), ('export', 'Export'), ('both', 'Import & Export'),
    ], string='Specialization', default='both')
    service_fee_type = fields.Selection([
        ('fixed', 'Fixed Amount'), ('percentage', 'Percentage of CIF'),
    ], string='Fee Type', default='fixed')
    service_fee = fields.Float(string='Service Fee')
    active      = fields.Boolean(default=True)
    notes       = fields.Text(string='Notes')

    clearance_count = fields.Integer(compute='_compute_clearance_count', string='Clearances')

    @api.depends('license_expiry_date')
    def _compute_license_expired(self):
        today = date.today()
        for r in self:
            r.license_expired = bool(r.license_expiry_date and r.license_expiry_date < today)

    def _compute_clearance_count(self):
        for r in self:
            r.clearance_count = self.env['customs.clearance'].search_count([('broker_id', '=', r.id)])

    def action_view_clearances(self):
        return {'name': 'Clearance Orders', 'type': 'ir.actions.act_window',
                'res_model': 'customs.clearance', 'view_mode': 'list,form',
                'domain': [('broker_id', '=', self.id)]}
