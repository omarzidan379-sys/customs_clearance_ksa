# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class CustomsPortalController(http.Controller):

    @http.route('/customs-portal', type='http', auth='public', website=True)
    def portal_home(self, **kwargs):
        return request.redirect('/customs-portal/register')

    @http.route('/customs-portal/register', type='http', auth='public', website=True)
    def portal_register(self, **kwargs):
        countries = request.env['res.country'].sudo().search([], order='name')
        return request.render('customs_clearance_ksa.portal_register_page', {
            'countries': countries,
            'page_title': 'Register Shipment — Customs Clearance Portal',
        })

    @http.route('/customs-portal/submit', type='http', auth='public', csrf=False, methods=['POST'], website=True)
    def portal_submit(self, **post):
        """
        Receives the JSON POST from the portal form.
        In Odoo 17, type='http' + read httprequest.data is the
        correct way to handle raw JSON bodies.
        type='json' was removed/changed and request.jsonrequest no longer exists.
        """
        try:
            # Read and parse the raw JSON body sent by the portal JS
            raw  = request.httprequest.data
            body = json.loads(raw) if raw else {}

            # The JS sends a JSON-RPC envelope: {jsonrpc, method, params:{...form data...}}
            # Unwrap the params layer to get the actual form fields
            data = body.get('params', body) if isinstance(body, dict) else {}

            # ── Validation ────────────────────────────────────────────────
            required = ['requester_name', 'requester_email',
                        'requester_company', 'clearance_type', 'goods_description']
            missing = [f for f in required if not data.get(f)]
            if missing:
                resp = {'success': False,
                        'error': 'Missing required fields: ' + ', '.join(missing)}
                return request.make_response(
                    json.dumps(resp),
                    headers=[('Content-Type', 'application/json')]
                )

            # ── Country helper ────────────────────────────────────────────
            def get_country(code):
                if not code:
                    return False
                c = request.env['res.country'].sudo().search(
                    [('code', '=', code)], limit=1)
                return c.id if c else False

            # ── Build record values ───────────────────────────────────────
            vals = {
                'request_type':           data.get('request_type', 'supplier'),
                'requester_name':         data.get('requester_name', ''),
                'requester_email':        data.get('requester_email', ''),
                'requester_phone':        data.get('requester_phone', ''),
                'requester_company':      data.get('requester_company', ''),
                'requester_cr_no':        data.get('requester_cr_no', ''),
                'requester_vat_no':       data.get('requester_vat_no', ''),
                'requester_country':      get_country(data.get('requester_country_code')),
                'requester_city':         data.get('requester_city', ''),
                'clearance_type':         data.get('clearance_type', 'import'),
                'shipment_type':          data.get('shipment_type', 'sea'),
                'country_origin_id':      get_country(data.get('country_origin_code')),
                'country_destination_id': get_country(data.get('country_destination_code')),
                'port_of_loading':        data.get('port_of_loading', ''),
                'port_of_discharge':      data.get('port_of_discharge', ''),
                'vessel_name':            data.get('vessel_name', ''),
                'bill_of_lading_no':      data.get('bill_of_lading_no', ''),
                'eta':                    data.get('eta') or False,
                'gross_weight':           float(data.get('gross_weight') or 0),
                'volume':                 float(data.get('volume') or 0),
                'packages_count':         int(data.get('packages_count') or 0),
                'goods_description':      data.get('goods_description', ''),
                'hs_codes_list':          data.get('hs_codes_list', ''),
                'estimated_value':        float(data.get('estimated_value') or 0),
                'currency_note':          data.get('currency_note', 'USD'),
                'has_bill_of_lading':     bool(data.get('has_bill_of_lading')),
                'has_invoice':            bool(data.get('has_invoice')),
                'has_packing_list':       bool(data.get('has_packing_list')),
                'has_coo':                bool(data.get('has_coo')),
                'has_saber_scoc':         bool(data.get('has_saber_scoc')),
                'has_sfda':               bool(data.get('has_sfda')),
                'has_citc':               bool(data.get('has_citc')),
                'additional_docs':        data.get('additional_docs', ''),
                'acd_reference_no':       data.get('acd_reference_no', ''),
                'saber_scoc_no':          data.get('saber_scoc_no', ''),
                'sfda_approval_no':       data.get('sfda_approval_no', ''),
                'fatoorah_invoice_no':    data.get('fatoorah_invoice_no', ''),
                'submission_ip':          request.httprequest.remote_addr,
            }

            portal_req = request.env['customs.portal.request'].sudo().create(vals)

            resp = {
                'success':   True,
                'reference': portal_req.name,
                'token':     portal_req.portal_token,
                'message':   'Request submitted. Reference: %s' % portal_req.name,
            }

        except Exception as e:
            _logger.error("Portal submission error: %s", str(e))
            resp = {'success': False, 'error': str(e)}

        return request.make_response(
            json.dumps(resp),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/customs-portal/status/<string:token>', type='http', auth='public', website=True)
    def portal_status(self, token, **kwargs):
        req = request.env['customs.portal.request'].sudo().search(
            [('portal_token', '=', token)], limit=1
        )
        if not req:
            return request.render('customs_clearance_ksa.portal_status_page', {
                'found': False, 'token': token,
            })
        return request.render('customs_clearance_ksa.portal_status_page', {
            'found': True,
            'req':   req,
            'token': token,
        })

    @http.route('/customs-portal/search', type='http', auth='public', website=True)
    def portal_search(self, **kwargs):
        """
        Search page: user enters name/phone + optional date filter.
        Returns all matching requests with live states.
        """
        name    = kwargs.get('name', '').strip()
        phone   = kwargs.get('phone', '').strip()
        date_from = kwargs.get('date_from', '').strip()
        date_to   = kwargs.get('date_to', '').strip()

        requests = []
        searched = bool(name or phone)

        if searched:
            domain = ['|',
                ('requester_name',    'ilike', name  or ' '),
                ('requester_phone',   'ilike', phone or ' '),
            ]
            if name and phone:
                domain = ['&',
                    ('requester_name',  'ilike', name),
                    ('requester_phone', 'ilike', phone),
                ]
            elif name:
                domain = [('requester_name',  'ilike', name)]
            elif phone:
                domain = [('requester_phone', 'ilike', phone)]

            if date_from:
                domain += [('create_date', '>=', date_from + ' 00:00:00')]
            if date_to:
                domain += [('create_date', '<=', date_to   + ' 23:59:59')]

            requests = request.env['customs.portal.request'].sudo().search(
                domain, order='create_date desc', limit=50
            )

        return request.render('customs_clearance_ksa.portal_search_page', {
            'requests':   requests,
            'searched':   searched,
            'name':       name,
            'phone':      phone,
            'date_from':  date_from,
            'date_to':    date_to,
        })