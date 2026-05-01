# -*- coding: utf-8 -*-
"""
Portal Live Tracking Controller
================================
Provides the bidirectional portal routes that portal clients use AFTER
their request is approved.  Clients receive the portal_token in the
approval email and can use it to track the live clearance state,
view required documents, and see their service invoice.

Routes added (all public, no Odoo session required):
  GET  /customs-portal/track/<token>    → Live clearance tracking page
  GET  /customs-portal/invoice/<token>  → Service invoice preview
  POST /customs-portal/track/ping       → AJAX poll for live status (JSON)
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Progress percentage per clearance state
_PROGRESS = {
    'draft':          5,
    'acd_submitted':  15,
    'submitted':      30,
    'customs_review': 45,
    'inspection':     60,
    'duty_payment':   75,
    'released':       90,
    'delivered':      100,
    'cancelled':      0,
}

# Timeline steps shown on the tracking page
_STEPS = [
    ('draft',          'Request Approved',         'طلب موافق عليه',       '✅'),
    ('acd_submitted',  'ACD Filed with Customs',   'تقديم بيان ACD',        '📋'),
    ('submitted',      'Filed with FASAH',         'تقديم في فساح',         '🏛️'),
    ('customs_review', 'Document Review',           'مراجعة المستندات',      '🔍'),
    ('inspection',     'Customs Inspection',        'الفحص الجمركي',         '🔬'),
    ('duty_payment',   'Duty Payment',              'سداد الرسوم الجمركية',  '💳'),
    ('released',       'Goods Released',            'تم الإفراج',            '📦'),
    ('delivered',      'Delivered',                 'تم التسليم',            '🚚'),
]

_STATE_ORDER = [s[0] for s in _STEPS]


class PortalTrackingController(http.Controller):

    # ── Live tracking page ────────────────────────────────────────────────────

    @http.route(
        '/customs-portal/track/<string:portal_token>',
        type='http', auth='public', website=False, csrf=False,
    )
    def track_shipment(self, portal_token, **kwargs):
        """Main tracking page — shows clearance timeline, documents, invoice."""
        PortalRequest = request.env['customs.portal.request'].sudo()
        portal_req = PortalRequest.search([('portal_token', '=', portal_token)], limit=1)

        clearance      = None
        service_invoice = None
        steps          = []
        progress_pct   = 0

        if portal_req and portal_req.clearance_id:
            clearance = portal_req.clearance_id
            progress_pct = _PROGRESS.get(clearance.state, 0)
            steps        = self._build_steps(clearance.state)

            service_invoice = request.env['customs.service.invoice'].sudo().search([
                ('clearance_id', '=', clearance.id),
                ('state', 'in', ('confirmed', 'sent', 'paid')),
            ], limit=1)

        return request.render('customs_clearance.portal_tracking_template', {
            'found':           bool(portal_req),
            'req':             portal_req,
            'clearance':       clearance,
            'invoice':         service_invoice,
            'token':           portal_token,
            'progress_pct':    progress_pct,
            'steps':           steps,
            'is_cancelled':    clearance and clearance.state == 'cancelled',
            'is_delivered':    clearance and clearance.state == 'delivered',
        })

    # ── Invoice preview page ──────────────────────────────────────────────────

    @http.route(
        '/customs-portal/invoice/<string:inv_token>',
        type='http', auth='public', website=False, csrf=False,
    )
    def view_invoice(self, inv_token, **kwargs):
        """Public invoice preview for portal clients."""
        invoice = request.env['customs.service.invoice'].sudo().search(
            [('portal_token', '=', inv_token)], limit=1
        )
        return request.render('customs_clearance.portal_invoice_template', {
            'found':   bool(invoice),
            'invoice': invoice,
        })

    # ── AJAX live status poll ─────────────────────────────────────────────────

    @http.route(
        '/customs-portal/track/ping',
        type='json', auth='public', csrf=False, methods=['POST'],
    )
    def ping_status(self, portal_token=None, **kwargs):
        """
        Called by the tracking page every 60 s to refresh status without
        a full page reload.  Returns state, progress, and lane info.
        """
        if not portal_token:
            return {'found': False}

        portal_req = request.env['customs.portal.request'].sudo().search(
            [('portal_token', '=', portal_token)], limit=1
        )
        if not portal_req or not portal_req.clearance_id:
            return {'found': bool(portal_req), 'state': portal_req.state if portal_req else None}

        clr = portal_req.clearance_id
        return {
            'found':        True,
            'state':        clr.state,
            'progress_pct': _PROGRESS.get(clr.state, 0),
            'lane':         clr.inspection_lane or 'unknown',
            'release_date': str(clr.actual_clearance_date) if clr.actual_clearance_date else None,
            'steps':        self._build_steps(clr.state),
        }

    # ── Helper ────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_steps(current_state):
        try:
            current_idx = _STATE_ORDER.index(current_state)
        except ValueError:
            current_idx = -1

        result = []
        for i, (key, label_en, label_ar, icon) in enumerate(_STEPS):
            try:
                step_idx = _STATE_ORDER.index(key)
            except ValueError:
                step_idx = i

            if current_state == 'cancelled':
                status = 'cancelled'
            elif step_idx < current_idx:
                status = 'done'
            elif step_idx == current_idx:
                status = 'active'
            else:
                status = 'pending'

            result.append({
                'key':      key,
                'label':    label_en,
                'label_ar': label_ar,
                'icon':     icon,
                'status':   status,
            })
        return result
