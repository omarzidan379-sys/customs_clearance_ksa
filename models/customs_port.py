# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CustomsPort(models.Model):
    _name = 'customs.port'
    _description = 'Port / Customs Office'
    _rec_name = 'name'
    _order = 'country_id, name'

    name = fields.Char(string='Name', required=True)
    name_ar = fields.Char(string='Arabic Name / الاسم بالعربي')
    code = fields.Char(string='Port Code / UN/LOCODE')
    port_type = fields.Selection([
        ('seaport', 'Seaport / ميناء بحري'),
        ('airport', 'Airport / مطار'),
        ('land_border', 'Land Border / معبر بري'),
        ('customs_office', 'Customs Office / مكتب جمارك'),
        ('dry_port', 'Dry Port / ميناء جاف'),
    ], string='Type', required=True, default='seaport')
    country_id = fields.Many2one('res.country', string='Country', required=True)
    city = fields.Char(string='City')
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')
