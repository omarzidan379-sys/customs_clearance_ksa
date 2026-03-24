# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CustomsHsCode(models.Model):
    _name = 'customs.hs.code'
    _description = 'HS Code — Saudi Harmonized System'
    _rec_name = 'display_name'
    _order = 'code'

    code        = fields.Char(string='HS Code', required=True)
    name        = fields.Char(string='Description (EN)', required=True)
    name_ar     = fields.Char(string='Description (AR) / الوصف')
    chapter     = fields.Char(string='Chapter',  compute='_compute_chapter',  store=True)
    heading     = fields.Char(string='Heading',  compute='_compute_heading',  store=True)
    display_name= fields.Char(compute='_compute_display_name', store=True)

    # Saudi duty rates
    import_duty_rate  = fields.Float(string='KSA Import Duty Rate (%)', digits=(5,2))
    export_duty_rate  = fields.Float(string='KSA Export Duty Rate (%)', digits=(5,2))
    vat_rate          = fields.Float(string='VAT Rate (%)',              digits=(5,2), default=15.0)
    excise_rate       = fields.Float(string='Excise Rate (%)',           digits=(5,2), default=0.0)
    gcc_duty_rate     = fields.Float(string='GCC Origin Duty Rate (%)',  digits=(5,2), default=0.0)

    # Saudi regulatory flags — auto-set compliance requirements
    requires_saber = fields.Boolean(string='Requires SABER Certificate',
        help='SASO SABER conformity certificate required at Saudi port.')
    requires_sfda  = fields.Boolean(string='Requires SFDA Approval',
        help='Saudi Food and Drug Authority approval required before import.')
    requires_citc  = fields.Boolean(string='Requires CITC Certificate',
        help='Communications, Space and Technology Commission certificate required.')
    requires_moi   = fields.Boolean(string='Requires MoI Permit',
        help='Ministry of Interior permit required (chemicals, controlled goods).')
    is_prohibited  = fields.Boolean(string='Prohibited in KSA',
        help='This commodity is prohibited from import/export in Saudi Arabia.')
    is_restricted  = fields.Boolean(string='Restricted in KSA',
        help='Requires special permit before import/export.')

    category           = fields.Char(string='Category')
    unit_of_quantity   = fields.Many2one('uom.uom', string='Statistical Unit')
    notes              = fields.Text(string='Notes')
    active             = fields.Boolean(default=True)

    @api.depends('code')
    def _compute_chapter(self):
        for r in self:
            r.chapter = r.code[:2] if r.code else False

    @api.depends('code')
    def _compute_heading(self):
        for r in self:
            r.heading = r.code[:4] if r.code else False

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for r in self:
            r.display_name = f'[{r.code}] {r.name}' if r.code else r.name

    _sql_constraints = [('code_unique', 'UNIQUE(code)', 'HS Code must be unique!')]
