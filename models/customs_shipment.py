# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class CustomsShipment(models.Model):
    _name = 'customs.shipment'
    _description = 'Customs Shipment / الشحنة الجمركية'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'departure_date desc, id desc'

    name = fields.Char(string='Shipment Reference', required=True, copy=False, tracking=True)

    shipment_type = fields.Selection([
        ('sea', 'Sea Freight / شحن بحري'),
        ('air', 'Air Freight / شحن جوي'),
        ('road', 'Road Freight / شحن بري'),
        ('rail', 'Rail Freight / شحن بالسكك الحديدية'),
    ], string='Shipment Type', required=True, default='sea', tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_transit', 'In Transit'),
        ('arrived', 'Arrived at Port'),
        ('cleared', 'Cleared'),
        ('delivered', 'Delivered'),
    ], string='State', default='draft', tracking=True)

    # ─── Vessel / Transport ──────────────────────────────────────────────────
    vessel_name = fields.Char(string='Vessel / Carrier Name')
    voyage_number = fields.Char(string='Voyage / Flight Number')
    container_ids = fields.One2many('customs.container', 'shipment_id', string='Containers')
    container_count = fields.Integer(compute='_compute_container_count', string='Containers')

    # ─── Ports ──────────────────────────────────────────────────────────────
    port_origin_id = fields.Many2one('customs.port', string='Port of Loading')
    port_destination_id = fields.Many2one('customs.port', string='Port of Discharge')

    # ─── Dates ──────────────────────────────────────────────────────────────
    departure_date = fields.Date(string='Departure Date', tracking=True)
    eta = fields.Date(string='ETA (Estimated Time of Arrival)', tracking=True)
    actual_arrival_date = fields.Date(string='Actual Arrival Date', tracking=True)

    # ─── Documents ──────────────────────────────────────────────────────────
    bill_of_lading_no = fields.Char(string='Bill of Lading / BL Number')
    master_bl_no = fields.Char(string='Master BL No.')
    house_bl_no = fields.Char(string='House BL No.')

    # ─── Weight & Volume ─────────────────────────────────────────────────────
    gross_weight = fields.Float(string='Gross Weight (kg)')
    net_weight = fields.Float(string='Net Weight (kg)')
    volume = fields.Float(string='Volume (CBM)')
    packages_count = fields.Integer(string='No. of Packages')

    # ─── Partner ─────────────────────────────────────────────────────────────
    shipper_id = fields.Many2one('res.partner', string='Shipper')
    consignee_id = fields.Many2one('res.partner', string='Consignee')
    notify_party_id = fields.Many2one('res.partner', string='Notify Party')

    # ─── Clearance Link ──────────────────────────────────────────────────────
    clearance_ids = fields.One2many('customs.clearance', 'shipment_id', string='Clearance Orders')
    clearance_count = fields.Integer(compute='_compute_clearance_count', string='Clearances')

    notes = fields.Text(string='Notes / ملاحظات')

    @api.depends('container_ids')
    def _compute_container_count(self):
        for rec in self:
            rec.container_count = len(rec.container_ids)

    @api.depends('clearance_ids')
    def _compute_clearance_count(self):
        for rec in self:
            rec.clearance_count = len(rec.clearance_ids)

    def action_view_clearances(self):
        return {
            'name': _('Clearance Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'customs.clearance',
            'view_mode': 'list,form',
            'domain': [('shipment_id', '=', self.id)],
        }


class CustomsContainer(models.Model):
    _name = 'customs.container'
    _description = 'Shipping Container'

    shipment_id = fields.Many2one('customs.shipment', string='Shipment', required=True, ondelete='cascade')
    container_number = fields.Char(string='Container No.', required=True)
    container_type = fields.Selection([
        ('20gp', "20' GP"),
        ('40gp', "40' GP"),
        ('40hc', "40' HC"),
        ('20rf', "20' Reefer"),
        ('40rf', "40' Reefer"),
        ('20ot', "20' Open Top"),
        ('lcl', 'LCL (Less Container Load)'),
    ], string='Container Type', default='20gp')
    seal_number = fields.Char(string='Seal No.')
    gross_weight = fields.Float(string='Gross Weight (kg)')
    volume = fields.Float(string='Volume (CBM)')
    notes = fields.Char(string='Notes')
