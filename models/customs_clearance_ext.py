# -*- coding: utf-8 -*-
"""
Customs Clearance Extensions — امتدادات نموذج التخليص
=======================================================
Extends customs.clearance (without modifying the original file) to add:
  - VIP/AEO customer detection and discount application
  - Smart-button counts for penalties, bonds, service invoices
  - Portal-client email notification on every state change
  - Shortcut actions for the new sub-objects
  - Service invoice creation wizard
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CustomsClearanceVipExt(models.Model):
    _inherit = 'customs.clearance'

    # ── VIP / AEO ─────────────────────────────────────────────────────────────
    vip_customer_id = fields.Many2one(
        'customs.vip.customer',
        string='VIP Profile',
        compute='_compute_vip_info',
        store=True,
    )
    is_vip = fields.Boolean(
        'VIP Client', compute='_compute_vip_info', store=True,
    )
    vip_tier = fields.Selection(
        related='vip_customer_id.vip_tier',
        string='VIP Tier',
        store=True,
    )
    vip_discount_applied = fields.Float('VIP Discount (%)', default=0.0)

    # ── Related object one2manys (for smart buttons & tabs) ───────────────────
    penalty_ids = fields.One2many(
        'customs.penalty', 'clearance_id', string='Penalties',
    )
    penalty_count = fields.Integer(compute='_compute_ext_counts', string='Penalties')

    bond_ids   = fields.One2many('customs.bond', 'clearance_id', string='Bonds')
    bond_count = fields.Integer(compute='_compute_ext_counts', string='Bonds')

    service_invoice_ids   = fields.One2many(
        'customs.service.invoice', 'clearance_id', string='Service Invoices',
    )
    service_invoice_count = fields.Integer(compute='_compute_ext_counts', string='Service Invoices')

    # ── Shipment cost lines ──────────────────────────────────────────────────
    cost_line_ids  = fields.One2many('customs.shipment.cost', 'clearance_id', string='Cost Lines')
    cost_line_count = fields.Integer(compute='_compute_ext_counts', string='Costs')

    # ── Financial summary (computed from cost lines + service invoices) ───────
    total_cost     = fields.Monetary(compute='_compute_financials', store=True, string='Total Costs')
    total_revenue  = fields.Monetary(compute='_compute_financials', store=True, string='Total Revenue')
    profit_amount  = fields.Monetary(compute='_compute_financials', store=True, string='Net Profit')
    profit_margin  = fields.Float(compute='_compute_financials', store=True, string='Profit Margin (%)')

    # ── Portal notification flag ───────────────────────────────────────────────
    portal_notif_count = fields.Integer(
        compute='_compute_portal_notif_count',
        string='Notifications Sent',
    )

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends('partner_id')
    def _compute_vip_info(self):
        for rec in self:
            vip = self.env['customs.vip.customer'].search(
                [('partner_id', '=', rec.partner_id.id), ('active', '=', True)], limit=1
            )
            rec.vip_customer_id = vip
            rec.is_vip          = bool(vip)

    @api.depends('penalty_ids', 'bond_ids', 'service_invoice_ids', 'cost_line_ids')
    def _compute_ext_counts(self):
        for rec in self:
            rec.penalty_count         = len(rec.penalty_ids)
            rec.bond_count            = len(rec.bond_ids)
            rec.service_invoice_count = len(rec.service_invoice_ids)
            rec.cost_line_count       = len(rec.cost_line_ids)

    @api.depends(
        'cost_line_ids.total_amount', 'cost_line_ids.state',
        'service_invoice_ids.total', 'service_invoice_ids.state',
        'total_duty_amount', 'port_charges', 'demurrage_fee',
    )
    def _compute_financials(self):
        for rec in self:
            # Revenue = confirmed/sent/paid service invoices
            revenue = sum(
                inv.total for inv in rec.service_invoice_ids
                if inv.state in ('confirmed', 'sent', 'paid')
            )
            # Costs = confirmed/billed/paid cost lines + existing duty/port/demurrage fields
            cost_lines = sum(
                c.total_amount for c in rec.cost_line_ids
                if c.state in ('confirmed', 'billed', 'paid')
            )
            legacy_costs = (rec.total_duty_amount or 0) + (rec.port_charges or 0) + (rec.demurrage_fee or 0)
            total_cost = cost_lines + (legacy_costs if not cost_lines else 0)

            rec.total_revenue = revenue
            rec.total_cost    = total_cost
            rec.profit_amount = revenue - total_cost
            rec.profit_margin = (rec.profit_amount / revenue * 100) if revenue > 0 else 0.0

    def _compute_portal_notif_count(self):
        for rec in self:
            rec.portal_notif_count = self.env['mail.message'].search_count([
                ('res_id', '=', rec.id),
                ('model', '=', 'customs.clearance'),
                ('subtype_id', '=', self.env.ref('mail.mt_note').id),
                ('body', 'ilike', '[Portal Notification]'),
            ])

    # ── write() — portal state-change notifications ───────────────────────────

    def write(self, vals):
        old_states = {rec.id: rec.state for rec in self}
        result = super().write(vals)

        if 'state' in vals:
            for rec in self:
                if old_states.get(rec.id) != rec.state:
                    rec._notify_portal_client_of_state_change(
                        old_states.get(rec.id), rec.state
                    )
                    # duty_payment → auto-create customs duty cost line
                    if rec.state == 'duty_payment':
                        try:
                            rec._auto_create_duty_cost_line()
                        except Exception as e:
                            _logger.warning(
                                'Could not auto-create duty cost for %s: %s', rec.name, e
                            )
                    # released → auto-create + confirm service invoice
                    if rec.state == 'released' and rec.partner_id:
                        try:
                            if not rec.service_invoice_ids:
                                inv = rec._auto_create_and_confirm_service_invoice()
                                _logger.info(
                                    'Auto-created service invoice %s for clearance %s.',
                                    inv.name, rec.name
                                )
                            else:
                                # Confirm any draft service invoices
                                for inv in rec.service_invoice_ids.filtered(
                                    lambda i: i.state == 'draft'
                                ):
                                    inv.action_confirm()
                        except Exception as e:
                            _logger.warning(
                                'Could not auto-confirm service invoice for %s: %s', rec.name, e
                            )
        return result

    def _notify_portal_client_of_state_change(self, old_state, new_state):
        """
        When a clearance moves to a new state, email the portal client
        who originally submitted the linked portal request (if any).
        """
        portal_req = self.env['customs.portal.request'].sudo().search(
            [('clearance_id', '=', self.id)], limit=1
        )
        if not portal_req or not portal_req.requester_email:
            return

        state_labels = dict(self._fields['state'].selection)
        new_label    = state_labels.get(new_state, new_state)

        subject = f'[Customs Clearance KSA] Update on your shipment — {self.name}'
        body    = f"""
<p>Dear {portal_req.requester_name},</p>
<p>Your customs clearance order <strong>{self.name}</strong> has been updated.</p>
<table style="border-collapse:collapse;width:100%;max-width:500px">
  <tr>
    <td style="padding:8px;background:#f0f9ff;font-weight:600">New Status</td>
    <td style="padding:8px"><strong>{new_label}</strong></td>
  </tr>
  <tr>
    <td style="padding:8px;background:#f0f9ff;font-weight:600">Reference</td>
    <td style="padding:8px">{self.name}</td>
  </tr>
  <tr>
    <td style="padding:8px;background:#f0f9ff;font-weight:600">Port</td>
    <td style="padding:8px">{self.port_id.name if self.port_id else '—'}</td>
  </tr>
</table>
<p>Track your shipment live: <a href="/customs-portal/track/{portal_req.portal_token}">Click here</a></p>
<p style="color:#64748b;font-size:12px">Customs Clearance KSA — ZATCA · FASAH · SABER Compliant</p>
"""
        self.message_post(
            body=f'[Portal Notification] Email sent to {portal_req.requester_email} — state: {new_label}',
            subtype_id=self.env.ref('mail.mt_note').id,
        )

        # Send email directly via mail.mail
        self.env['mail.mail'].sudo().create({
            'subject':    subject,
            'body_html':  body,
            'email_to':   portal_req.requester_email,
            'auto_delete': True,
        }).send()

    def _auto_create_duty_cost_line(self):
        """
        When clearance reaches duty_payment state, auto-create a confirmed
        customs duty cost line from total_duty_amount. Skips if already present.
        """
        self.ensure_one()
        if not self.total_duty_amount:
            return
        existing = self.cost_line_ids.filtered(lambda c: c.cost_type == 'customs_duty')
        if existing:
            return
        cost = self.env['customs.shipment.cost'].create({
            'clearance_id': self.id,
            'name':         'Customs Duty — %s' % self.name,
            'cost_type':    'customs_duty',
            'amount':       self.total_duty_amount,
            'vat_exempt':   True,
        })
        cost.action_confirm()
        _logger.info('Auto-created customs duty cost SAR %.2f for %s.', self.total_duty_amount, self.name)

    def _auto_create_and_confirm_service_invoice(self):
        """
        Create, populate, and confirm a service invoice for this clearance.
        Returns the confirmed invoice.
        """
        self.ensure_one()
        inv = self.env['customs.service.invoice'].create({
            'clearance_id': self.id,
            'partner_id':   self.partner_id.id,
            'invoice_date': fields.Date.today(),
        })
        inv.action_populate_from_clearance()
        if inv.line_ids:
            inv.action_confirm()
        return inv

    # ── VIP discount auto-apply ───────────────────────────────────────────────

    @api.onchange('partner_id')
    def _onchange_partner_apply_vip(self):
        """Auto-apply VIP discount when partner changes."""
        if self.vip_customer_id and not self.vip_discount_applied:
            self.vip_discount_applied = self.vip_customer_id.service_fee_discount
        if self.vip_customer_id and self.vip_customer_id.priority_processing:
            self.priority = '2'  # Very Urgent
        if self.vip_customer_id and self.vip_customer_id.dedicated_broker_id:
            self.broker_id = self.vip_customer_id.dedicated_broker_id

    # ── Smart button actions ──────────────────────────────────────────────────

    def action_view_penalties(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Penalties — {self.name}',
            'res_model': 'customs.penalty',
            'view_mode': 'list,form',
            'domain': [('clearance_id', '=', self.id)],
            'context': {
                'default_clearance_id': self.id,
                'default_partner_id':   self.partner_id.id,
            },
        }

    def action_view_bonds(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Bonds — {self.name}',
            'res_model': 'customs.bond',
            'view_mode': 'list,form',
            'domain': [('clearance_id', '=', self.id)],
            'context': {
                'default_clearance_id': self.id,
                'default_partner_id':   self.partner_id.id,
            },
        }

    def action_view_service_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Service Invoices — {self.name}',
            'res_model': 'customs.service.invoice',
            'view_mode': 'list,form',
            'domain': [('clearance_id', '=', self.id)],
            'context': {
                'default_clearance_id': self.id,
                'default_partner_id':   self.partner_id.id,
            },
        }

    def action_create_service_invoice(self):
        """Create and auto-populate a service invoice from this clearance."""
        self.ensure_one()
        inv = self.env['customs.service.invoice'].create({
            'clearance_id': self.id,
            'partner_id':   self.partner_id.id,
            'invoice_date': fields.Date.today(),
        })
        inv.action_populate_from_clearance()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'customs.service.invoice',
            'res_id': inv.id,
            'view_mode': 'form',
        }

    def action_view_cost_lines(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      f'Costs — {self.name}',
            'res_model': 'customs.shipment.cost',
            'view_mode': 'list,form',
            'domain':    [('clearance_id', '=', self.id)],
            'context':   {'default_clearance_id': self.id},
        }

    def action_create_bond(self):
        """Quick-create a bond linked to this clearance."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Bond',
            'res_model': 'customs.bond',
            'view_mode': 'form',
            'context': {
                'default_clearance_id': self.id,
                'default_partner_id':   self.partner_id.id,
            },
        }
