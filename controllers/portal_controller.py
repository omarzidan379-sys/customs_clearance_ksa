# -*- coding: utf-8 -*-
from odoo import fields, http, _
from odoo.http import request
import json
import base64
import logging

_logger = logging.getLogger(__name__)


class CustomsPortalController(http.Controller):

    @http.route('/customs-portal', type='http', auth='public', website=True)
    def portal_home(self, **kwargs):
        return request.redirect('/customs-portal/register')

    @http.route('/customs-portal/register', type='http', auth='public', website=True)
    def portal_register(self, **kwargs):
        countries = request.env['res.country'].sudo().search([], order='name')
        return request.render('customs_clearance.portal_register_page', {
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

            # ── Real-time notification to all customs staff ───────────────
            try:
                customs_group = request.env.ref(
                    'customs_clearance.group_customs_user', raise_if_not_found=False)
                if customs_group:
                    partners = customs_group.sudo().users.mapped('partner_id')
                    notif_msg = (
                        '🚢 New Portal Request: <b>%s</b><br/>'
                        'From: %s (%s)<br/>'
                        'Type: %s | Company: %s'
                    ) % (
                        portal_req.name,
                        vals.get('requester_name', ''),
                        vals.get('requester_email', ''),
                        vals.get('clearance_type', '').upper(),
                        vals.get('requester_company', ''),
                    )
                    # Post on the record chatter so staff see it
                    portal_req.message_post(
                        body=notif_msg,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                    # Bus real-time pop-up for each online customs user
                    notifications = []
                    for partner in partners:
                        notifications.append((
                            partner,
                            'simple_notification',
                            {
                                'title': '📦 New Portal Request',
                                'message': '%s submitted a new %s clearance request.' % (
                                    vals.get('requester_name', 'A customer'),
                                    vals.get('clearance_type', 'import'),
                                ),
                                'warning': False,
                                'sticky': False,
                            }
                        ))
                    if notifications:
                        request.env['bus.bus'].sudo()._sendmany(notifications)
            except Exception as notify_err:
                _logger.warning("Portal notification error: %s", notify_err)

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

    @http.route('/customs-portal/status', type='http', auth='public', website=True)
    def portal_status_home(self, **kwargs):
        """Status page without token — show a token entry form."""
        return request.render('customs_clearance.portal_status_entry_page', {})

    @http.route('/customs-portal/status-search', type='http', auth='public', website=True)
    def portal_status_search(self, ref='', **kwargs):
        """Redirect to the status page for the entered reference/token."""
        ref = ref.strip()
        if not ref:
            return request.redirect('/customs-portal/status')
        req = request.env['customs.portal.request'].sudo().search([
            '|',
            ('portal_token', '=', ref),
            ('name', '=', ref),
        ], limit=1)
        if req:
            return request.redirect('/customs-portal/status/%s' % req.portal_token)
        return request.render('customs_clearance.portal_status_page', {
            'found': False, 'token': ref,
        })

    @http.route('/customs-portal/status/<string:token>', type='http', auth='public', website=True)
    def portal_status(self, token, **kwargs):
        req = request.env['customs.portal.request'].sudo().search(
            [('portal_token', '=', token)], limit=1
        )
        if not req:
            return request.render('customs_clearance.portal_status_page', {
                'found': False, 'token': token,
            })

        clearance = req.clearance_id or None
        steps = []
        progress_pct = 0

        if clearance:
            _STEPS_DEF = [
                ('draft',          'Approved',        'موافق عليه'),
                ('acd_submitted',  'ACD Filed',       'تقديم ACD'),
                ('submitted',      'FASAH Filed',     'تقديم فساح'),
                ('customs_review', 'Doc Review',      'مراجعة'),
                ('inspection',     'Inspection',      'الفحص'),
                ('duty_payment',   'Duty Payment',    'سداد الرسوم'),
                ('released',       'Released',        'الإفراج'),
                ('delivered',      'Delivered',       'التسليم'),
            ]
            _STATE_ORDER = [s[0] for s in _STEPS_DEF]
            _PROGRESS_MAP = {
                'draft': 5, 'acd_submitted': 15, 'submitted': 30,
                'customs_review': 45, 'inspection': 60,
                'duty_payment': 75, 'released': 90, 'delivered': 100,
            }
            progress_pct = _PROGRESS_MAP.get(clearance.state, 0)
            try:
                cur_idx = _STATE_ORDER.index(clearance.state)
            except ValueError:
                cur_idx = -1
            for i, (key, lbl_en, lbl_ar) in enumerate(_STEPS_DEF):
                try:
                    idx = _STATE_ORDER.index(key)
                except ValueError:
                    idx = i
                if clearance.state == 'cancelled':
                    status = 'cancelled'
                elif idx < cur_idx:
                    status = 'done'
                elif idx == cur_idx:
                    status = 'active'
                else:
                    status = 'pending'
                steps.append({'key': key, 'label': lbl_en, 'label_ar': lbl_ar, 'status': status})

        return request.render('customs_clearance.portal_status_page', {
            'found':        True,
            'req':          req,
            'clearance':    clearance,
            'token':        token,
            'steps':        steps,
            'progress_pct': progress_pct,
        })

    @http.route('/customs-portal/offer/accept/<string:token>', type='http', auth='public', website=True)
    def offer_accept(self, token, **kwargs):
        req = request.env['customs.portal.request'].sudo().search(
            [('offer_token', '=', token)], limit=1
        )
        if not req:
            return request.render('customs_clearance.portal_offer_response_page', {
                'success': False,
                'action':  'accept',
                'message': 'Invalid or expired offer link.',
            })
        if req.offer_state == 'accepted':
            return request.render('customs_clearance.portal_offer_response_page', {
                'success': True,
                'action':  'accept',
                'already': True,
                'req':     req,
            })
        req.sudo().write({
            'offer_state':        'accepted',
            'offer_replied_date': fields.Datetime.now(),
        })
        req.message_post(body='Customer accepted the service offer via portal link.')
        # Auto-create service invoice for the linked clearance if it exists
        if req.clearance_id and req.clearance_id.partner_id:
            try:
                clr = req.clearance_id
                if not clr.service_invoice_ids:
                    inv = request.env['customs.service.invoice'].sudo().create({
                        'clearance_id': clr.id,
                        'partner_id':   clr.partner_id.id,
                        'invoice_date': fields.Date.today(),
                    })
                    inv.sudo().action_populate_from_clearance()
                    _logger.info('Auto-created service invoice %s after customer accepted offer.', inv.name)
            except Exception as e:
                _logger.warning('Could not create service invoice after offer accept: %s', e)
        return request.render('customs_clearance.portal_offer_response_page', {
            'success': True,
            'action':  'accept',
            'already': False,
            'req':     req,
        })

    @http.route('/customs-portal/offer/reject/<string:token>', type='http', auth='public', website=True)
    def offer_reject(self, token, **kwargs):
        req = request.env['customs.portal.request'].sudo().search(
            [('offer_token', '=', token)], limit=1
        )
        if not req:
            return request.render('customs_clearance.portal_offer_response_page', {
                'success': False,
                'action':  'reject',
                'message': 'Invalid or expired offer link.',
            })
        if req.offer_state in ('accepted', 'rejected'):
            return request.render('customs_clearance.portal_offer_response_page', {
                'success': True,
                'action':  req.offer_state,
                'already': True,
                'req':     req,
            })
        req.sudo().write({
            'offer_state':        'rejected',
            'offer_replied_date': fields.Datetime.now(),
        })
        req.message_post(body='Customer declined the service offer via portal link.')
        return request.render('customs_clearance.portal_offer_response_page', {
            'success': True,
            'action':  'reject',
            'already': False,
            'req':     req,
        })

    @http.route('/customs-portal/upload-doc', type='http', auth='public', csrf=False, methods=['POST'], website=True)
    def portal_upload_doc(self, **post):
        """Receive a file upload for a portal request identified by token."""
        try:
            token     = request.httprequest.form.get('token', '').strip()
            doc_field = request.httprequest.form.get('doc_field', '').strip()
            file_obj  = request.httprequest.files.get('file')

            if not token or not file_obj:
                return request.make_response(
                    json.dumps({'success': False, 'error': 'Missing token or file'}),
                    headers=[('Content-Type', 'application/json')]
                )

            portal_req = request.env['customs.portal.request'].sudo().search(
                [('portal_token', '=', token)], limit=1
            )
            if not portal_req:
                return request.make_response(
                    json.dumps({'success': False, 'error': 'Request not found'}),
                    headers=[('Content-Type', 'application/json')]
                )

            file_data = file_obj.read()
            filename  = file_obj.filename or (doc_field + '_upload')

            attachment = request.env['ir.attachment'].sudo().create({
                'name':      filename,
                'datas':     base64.b64encode(file_data).decode('utf-8'),
                'res_model': 'customs.portal.request',
                'res_id':    portal_req.id,
                'mimetype':  file_obj.content_type or 'application/octet-stream',
            })
            portal_req.sudo().write({'attachment_ids': [(4, attachment.id)]})

            resp = {'success': True, 'attachment_id': attachment.id}
        except Exception as e:
            _logger.error("Portal upload error: %s", str(e))
            resp = {'success': False, 'error': str(e)}

        return request.make_response(
            json.dumps(resp),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/customs-portal/doc/<string:token>/<int:att_id>', type='http', auth='public', website=True)
    def portal_download_doc(self, token, att_id, **kwargs):
        """Serve an attachment file using the portal token for auth."""
        portal_req = request.env['customs.portal.request'].sudo().search(
            [('portal_token', '=', token)], limit=1
        )
        if not portal_req:
            return request.not_found()

        attachment = request.env['ir.attachment'].sudo().search([
            ('id', '=', att_id),
            ('res_model', '=', 'customs.portal.request'),
            ('res_id', '=', portal_req.id),
        ], limit=1)
        if not attachment or attachment.id not in portal_req.attachment_ids.ids:
            return request.not_found()

        file_data = base64.b64decode(attachment.datas)
        return request.make_response(
            file_data,
            headers=[
                ('Content-Type', attachment.mimetype or 'application/octet-stream'),
                ('Content-Disposition', 'attachment; filename="%s"' % attachment.name),
                ('Content-Length', str(len(file_data))),
            ]
        )

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

        return request.render('customs_clearance.portal_search_page', {
            'requests':   requests,
            'searched':   searched,
            'name':       name,
            'phone':      phone,
            'date_from':  date_from,
            'date_to':    date_to,
        })

    # ── Shipment Tracking Dashboard ───────────────────────────────────────────

    # Known coordinates for major Saudi / international ports (UN/LOCODE → [lat, lon])
    _PORT_COORDS = {
        'SAJED': [21.4858, 39.1925],  # Jeddah Islamic Port
        'SADMM': [26.4207, 50.1031],  # Dammam King Abdul Aziz Port
        'SARIY': [24.6877, 46.7219],  # Riyadh Dry Port
        'SAYNB': [23.6150, 38.0627],  # Yanbu Industrial Port
        'SAGJN': [16.8894, 42.5638],  # Gizan / Jizan Port
        'SAQIS': [28.4563, 34.7864],  # Aqaba (Haql border area)
        'AEDXB': [25.2532, 55.3657],  # Dubai Jebel Ali
        'AEJEA': [24.9964, 55.0600],  # Jebel Ali
        'BHMUH': [26.2172, 50.6480],  # Bahrain Muharraq
        'CNSHA': [31.2304, 121.4737], # Shanghai
        'CNNGB': [29.8683, 121.5440], # Ningbo
        'CNSZX': [22.5431, 114.0579], # Shenzhen
        'CNTAO': [36.0671, 120.3826], # Qingdao
        'USNYC': [40.6840, -74.0440], # New York
        'USLAX': [33.7395, -118.2596],# Los Angeles
        'DEHAM': [53.5511, 9.9937],   # Hamburg
        'NLRTM': [51.9244, 4.4777],   # Rotterdam
        'SGSIN': [1.2897, 103.8501],  # Singapore
        'INMAA': [13.0827, 80.2707],  # Chennai
        'INBOM': [18.9322, 72.8264],  # Mumbai
        'PKKAR': [24.8607, 67.0011],  # Karachi
        'TRIST': [41.0082, 28.9784],  # Istanbul
        'EGPSD': [31.2357, 32.3051],  # Port Said
        'GBFXT': [51.8761, 1.2875],   # Felixstowe UK
    }

    def _get_port_coords(self, port_name):
        """Return [lat, lon] for a port name string, matching against known ports."""
        if not port_name:
            return None
        name_upper = (port_name or '').upper().strip()
        # Direct code match
        if name_upper in self._PORT_COORDS:
            return self._PORT_COORDS[name_upper]
        # Partial name match against known port keywords
        _PORT_KEYWORDS = {
            'JEDDAH': [21.5433, 39.1728], 'JEDDA': [21.5433, 39.1728],
            'DAMMAM': [26.4207, 50.0888], 'KING ABDULAZIZ': [26.4207, 50.0888],
            'RIYADH': [24.7136, 46.6753],
            'JUBAIL': [27.0046, 49.6617],
            'YANBU': [24.0884, 38.0618],
            'AQABA': [29.5267, 35.0078],
            'DUBAI': [25.2048, 55.2708], 'UAE': [25.2048, 55.2708],
            'ABU DHABI': [24.4539, 54.3773],
            'MUSCAT': [23.5880, 58.3829],
            'BAHRAIN': [26.2154, 50.5860],
            'KUWAIT': [29.3759, 47.9774],
            'DOHA': [25.2854, 51.5310], 'QATAR': [25.2854, 51.5310],
            'SINGAPORE': [1.2897, 103.8501],
            'HONG KONG': [22.3193, 114.1694],
            'SHANGHAI': [31.2304, 121.4737],
            'ROTTERDAM': [51.9244, 4.4777],
            'HAMBURG': [53.5511, 9.9937],
            'PORT SAID': [31.2357, 32.3051],
            'SUEZ': [29.9668, 32.5498],
            'MUMBAI': [18.9322, 72.8264], 'BOMBAY': [18.9322, 72.8264],
            'KARACHI': [24.8607, 67.0011],
            'ISTANBUL': [41.0082, 28.9784],
            'ANTWERP': [51.2213, 4.4051],
            'FELIXSTOWE': [51.8761, 1.2875],
            'BRAZIL': [-15.7801, -47.9292],
            'CHINA': [35.8617, 104.1954],
            'INDIA': [20.5937, 78.9629],
        }
        for keyword, coords in _PORT_KEYWORDS.items():
            if keyword in name_upper:
                return coords
        return None

    def _build_timeline(self, req, clearance, shipment):
        """Build timeline events from portal request + clearance state history."""
        from odoo import fields as odoo_fields
        events = []

        # Step 1: Request submitted
        events.append({
            'date': req.create_date.date() if req.create_date else None,
            'time': req.create_date.strftime('%H:%M') if req.create_date else '',
            'location': req.requester_city or req.requester_company or 'Client',
            'description': 'Clearance Request Submitted',
            'description_ar': 'تم تقديم طلب التخليص',
            'icon': 'fa-paper-plane',
            'color': '#0d6efd',
            'done': True,
        })

        # Step 2: Approved or Rejected
        _REQ_STATE = {
            'draft':    ('Request Under Review', 'fa-clock-o', '#fd7e14', 'قيد المراجعة'),
            'approved': ('Request Approved — Clearance Started', 'fa-check-circle', '#198754', 'تمت الموافقة'),
            'rejected': ('Request Rejected', 'fa-times-circle', '#dc3545', 'مرفوض'),
        }
        if req.state != 'draft':
            lbl = _REQ_STATE.get(req.state, ('Status Updated', 'fa-circle', '#6c757d', ''))
            events.append({
                'date': req.review_date.date() if getattr(req, 'review_date', None) and req.review_date else None,
                'time': req.review_date.strftime('%H:%M') if getattr(req, 'review_date', None) and req.review_date else '',
                'location': 'Customs Clearance Office',
                'description': lbl[0],
                'description_ar': lbl[3],
                'icon': lbl[1],
                'color': lbl[2],
                'done': True,
            })

        # Step 3: Clearance stages (from linked clearance record)
        if clearance:
            _CL_STATES = [
                ('acd_submitted',  'ACD Filed with Saudi Customs', 'fa-file-text', '#0d6efd', 'تقديم ACD للجمارك'),
                ('submitted',      'FASAH Declaration Submitted', 'fa-send', '#0d6efd', 'إدخال البيان في فساح'),
                ('customs_review', 'Under Customs Review', 'fa-search', '#fd7e14', 'قيد مراجعة الجمارك'),
                ('inspection',     'Physical Inspection in Progress', 'fa-eye', '#fd7e14', 'جاري الفحص المادي'),
                ('duty_payment',   'Duty Payment Required', 'fa-credit-card', '#ffc107', 'مطلوب سداد الجمارك'),
                ('released',       'Customs Released ✓', 'fa-unlock', '#198754', 'الإفراج الجمركي'),
                ('delivered',      'Delivered to Consignee ✓', 'fa-flag-checkered', '#198754', 'تم التسليم'),
                ('refused',        'Refused by Customs', 'fa-ban', '#dc3545', 'مرفوض جمركياً'),
                ('cancelled',      'Cancelled', 'fa-times', '#dc3545', 'ملغى'),
            ]
            state_order = [s[0] for s in _CL_STATES]
            current_idx = state_order.index(clearance.state) if clearance.state in state_order else -1

            for i, (state_key, label, icon, color, label_ar) in enumerate(_CL_STATES):
                is_done = (i <= current_idx) and clearance.state not in ('refused', 'cancelled')
                is_active = (i == current_idx)
                if is_done or is_active:
                    events.append({
                        'date': None,
                        'time': '',
                        'location': (clearance.customs_office_id.name if clearance.customs_office_id else '') or 'Saudi Customs',
                        'description': label,
                        'description_ar': label_ar,
                        'icon': icon,
                        'color': color,
                        'done': is_done,
                        'active': is_active,
                    })

        # Step 4: Shipment events
        if shipment:
            if shipment.departure_date:
                events.append({
                    'date': shipment.departure_date,
                    'time': '00:00',
                    'location': shipment.port_origin_id.name if shipment.port_origin_id else 'Origin Port',
                    'description': 'Departed from %s' % (shipment.port_origin_id.name or 'Origin'),
                    'icon': 'fa-ship',
                    'color': '#0d6efd',
                    'done': True,
                })
            if shipment.eta:
                events.append({
                    'date': shipment.eta,
                    'time': '00:00',
                    'location': shipment.port_destination_id.name if shipment.port_destination_id else 'Destination Port',
                    'description': 'ETA at %s' % (shipment.port_destination_id.name or 'Destination'),
                    'icon': 'fa-flag',
                    'color': '#198754' if shipment.state == 'delivered' else '#6c757d',
                    'done': shipment.state in ('arrived', 'cleared', 'delivered'),
                })

        return events

    def _calc_progress(self, req, clearance, shipment):
        """Return integer 0-100 progress percentage based on best available state."""
        if shipment:
            _PROG = {'draft': 15, 'in_transit': 45, 'arrived': 70, 'cleared': 88, 'delivered': 100}
            return _PROG.get(shipment.state, 15)
        if clearance:
            _PROG = {
                'draft': 15, 'acd_submitted': 30, 'submitted': 45,
                'customs_review': 55, 'inspection': 65, 'duty_payment': 75,
                'released': 90, 'delivered': 100, 'refused': 5, 'cancelled': 5,
            }
            return _PROG.get(clearance.state, 15)
        if req:
            _PROG = {'draft': 10, 'approved': 20, 'rejected': 5}
            return _PROG.get(req.state, 10)
        return 0

    @http.route('/customs-portal/tracking', type='http', auth='public', website=True)
    def portal_tracking_home(self, ref='', **kwargs):
        """Tracking search landing page — enter reference to look up shipment."""
        error = None
        if ref:
            portal_req = request.env['customs.portal.request'].sudo().search(
                [('portal_token', '=', ref.strip())], limit=1
            )
            if not portal_req:
                portal_req = request.env['customs.portal.request'].sudo().search(
                    [('name', '=', ref.strip())], limit=1
                )
            if portal_req:
                return request.redirect('/customs-portal/tracking/' + portal_req.portal_token)
            error = 'No shipment found for reference: %s' % ref.strip()
        return request.render('customs_clearance.portal_tracking_search', {
            'ref': ref,
            'error': error,
        })

    @http.route('/customs-portal/tracking/<string:token>', type='http', auth='public', website=True)
    def portal_tracking_detail(self, token, **kwargs):
        """Modern shipment tracking dashboard — pulls data from portal request."""
        portal_req = request.env['customs.portal.request'].sudo().search(
            [('portal_token', '=', token)], limit=1
        )
        if not portal_req:
            return request.render('customs_clearance.portal_tracking_detail', {
                'found': False, 'token': token,
            })

        clearance = portal_req.clearance_id or None
        shipment  = (clearance.shipment_id if clearance else None) or None

        # Resolve port names — prefer shipment record, fall back to portal request text fields
        origin_name = (
            (shipment.port_origin_id.name if shipment and shipment.port_origin_id else None)
            or portal_req.port_of_loading or ''
        )
        dest_name = (
            (shipment.port_destination_id.name if shipment and shipment.port_destination_id else None)
            or portal_req.port_of_discharge or ''
        )

        origin_coords = self._get_port_coords(origin_name) or [24.7136, 46.6753]
        dest_coords   = self._get_port_coords(dest_name)   or [21.5433, 39.1728]

        # Current ship position
        ship_state = shipment.state if shipment else None
        req_done   = portal_req.state in ('approved',)
        if ship_state == 'in_transit':
            current_coords = [
                round((origin_coords[0] + dest_coords[0]) / 2, 4),
                round((origin_coords[1] + dest_coords[1]) / 2, 4),
            ]
        elif ship_state in ('arrived', 'cleared', 'delivered'):
            current_coords = dest_coords
        elif req_done and clearance and clearance.state in ('released', 'delivered'):
            current_coords = dest_coords
        else:
            current_coords = origin_coords

        timeline = self._build_timeline(portal_req, clearance, shipment)
        progress = self._calc_progress(portal_req, clearance, shipment)

        return request.render('customs_clearance.portal_tracking_detail', {
            'found':          True,
            'token':          token,
            'req':            portal_req,
            'clearance':      clearance,
            'shipment':       shipment,
            'timeline':       timeline,
            'progress':       progress,
            'origin_name':    origin_name or 'Origin',
            'dest_name':      dest_name   or 'Destination',
            'origin_coords':  origin_coords,
            'dest_coords':    dest_coords,
            'current_coords': current_coords,
        })
    @http.route('/customs-portal/contract', type='http', auth='public', website=True)
    def portal_contract_page(self, **kwargs):
        """Printable service contract terms page."""
        company = request.env['res.company'].sudo().search([], limit=1)
        return request.render('customs_clearance.portal_contract_template', {
            'company': company,
        })
