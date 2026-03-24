# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class CustomsDocumentType(models.Model):
    _name = 'customs.document.type'
    _description = 'Customs Document Type'
    _order = 'sequence, name'

    name = fields.Char(string='Document Type', required=True, translate=True)
    code = fields.Char(string='Code')
    sequence = fields.Integer(default=10)
    required = fields.Boolean(string='Required', default=False)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)


class CustomsDocument(models.Model):
    _name = 'customs.document'
    _description = 'Customs Document'
    _inherit = ['mail.thread']
    _rec_name = 'name'

    clearance_id = fields.Many2one(
        'customs.clearance', string='Clearance Order',
        required=True, ondelete='cascade',
    )
    name = fields.Char(string='Document Name', required=True)
    document_type_id = fields.Many2one('customs.document.type', string='Document Type', required=True)
    document_number = fields.Char(string='Document Number / Reference')

    state = fields.Selection([
        ('pending', 'Pending / مطلوب'),
        ('received', 'Received / مستلم'),
        ('verified', 'Verified / مُحقَّق'),
        ('rejected', 'Rejected / مرفوض'),
    ], string='Status', default='pending', tracking=True)

    issue_date = fields.Date(string='Issue Date')
    expiry_date = fields.Date(string='Expiry Date')
    issuing_authority = fields.Char(string='Issuing Authority')

    attachment_ids = fields.Many2many(
        'ir.attachment', string='Attachments',
        relation='customs_document_attachment_rel',
    )
    attachment_count = fields.Integer(compute='_compute_attachment_count')

    notes = fields.Text(string='Notes')

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_ids)

    def action_receive(self):
        self.write({'state': 'received'})

    def action_verify(self):
        self.write({'state': 'verified'})

    def action_reject(self):
        self.write({'state': 'rejected'})
