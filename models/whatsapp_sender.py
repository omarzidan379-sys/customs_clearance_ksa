# -*- coding: utf-8 -*-
"""
WhatsApp notification service for Customs Clearance KSA.

Supported providers:
  - waha      : WAHA self-hosted (https://waha.devlike.pro) — most popular self-hosted
  - ultramsg  : UltraMsg cloud API (https://ultramsg.com)
  - twilio    : Twilio WhatsApp (https://twilio.com)
  - custom    : Any HTTP API (POST JSON)

Config keys (ir.config_parameter):
  customs.whatsapp.enabled        : '1' / '0'
  customs.whatsapp.provider       : waha | ultramsg | twilio | custom
  customs.whatsapp.endpoint       : API base URL
  customs.whatsapp.token          : API key / auth token
  customs.whatsapp.from_number    : Sender number (intl format: +966XXXXXXXXX)
  customs.whatsapp.admin_number   : Admin phone to receive new-request alerts
  customs.whatsapp.twilio_sid     : Twilio Account SID (Twilio only)
  customs.whatsapp.waha_session   : WAHA session name (default: 'default')
  customs.whatsapp.notify_new     : '1' send admin WA on new portal request
  customs.whatsapp.notify_approve : '1' send client WA on approval
  customs.whatsapp.notify_reject  : '1' send client WA on rejection
  customs.whatsapp.notify_offer   : '1' send client WA on offer
"""

import json
import logging
import requests

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

_PARAM = 'customs.whatsapp.'


class WhatsAppSender(models.AbstractModel):
    _name = 'customs.whatsapp.sender'
    _description = 'WhatsApp Notification Sender'

    # ── Config helpers ────────────────────────────────────────────────────

    def _wa_param(self, key, default=''):
        return self.env['ir.config_parameter'].sudo().get_param(_PARAM + key, default)

    def _wa_enabled(self):
        return self._wa_param('enabled', '0') == '1'

    def _wa_provider(self):
        return self._wa_param('provider', 'waha')

    # ── Public send API ───────────────────────────────────────────────────

    def send_whatsapp(self, to_number, message):
        """
        Send a WhatsApp text message.

        :param to_number: recipient in international format e.g. +966501234567
        :param message:   plain text body
        :return: True on success, False on failure
        """
        if not self._wa_enabled():
            return False
        if not to_number or not message:
            return False

        to_number = self._normalize_number(to_number)
        provider   = self._wa_provider()

        try:
            if provider == 'waha':
                return self._send_waha(to_number, message)
            elif provider == 'ultramsg':
                return self._send_ultramsg(to_number, message)
            elif provider == 'twilio':
                return self._send_twilio(to_number, message)
            else:
                return self._send_custom(to_number, message)
        except Exception as e:
            _logger.error('WhatsApp send failed (%s): %s', provider, e)
            return False

    # ── Provider implementations ──────────────────────────────────────────

    def _send_waha(self, to, message):
        """WAHA: POST /api/sendText"""
        endpoint = self._wa_param('endpoint', '').rstrip('/')
        token    = self._wa_param('token', '')
        session  = self._wa_param('waha_session', 'default')

        if not endpoint:
            _logger.warning('WhatsApp WAHA: no endpoint configured')
            return False

        # WAHA chat ID format: 966XXXXXXXXX@c.us (no leading +)
        chat_id = to.lstrip('+') + '@c.us'

        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-Api-Key'] = token

        payload = {'chatId': chat_id, 'text': message, 'session': session}
        resp = requests.post(
            '%s/api/sendText' % endpoint,
            json=payload, headers=headers, timeout=15
        )
        if resp.status_code in (200, 201):
            _logger.info('WhatsApp WAHA sent to %s', to)
            return True
        _logger.warning('WhatsApp WAHA error %s: %s', resp.status_code, resp.text[:200])
        return False

    def _send_ultramsg(self, to, message):
        """UltraMsg: POST /instance{ID}/messages/chat"""
        endpoint  = self._wa_param('endpoint', '').rstrip('/')
        token     = self._wa_param('token', '')

        if not endpoint or not token:
            _logger.warning('WhatsApp UltraMsg: endpoint or token missing')
            return False

        payload = {'token': token, 'to': to, 'body': message}
        resp = requests.post(
            '%s/messages/chat' % endpoint,
            data=payload, timeout=15
        )
        data = resp.json() if resp.content else {}
        if data.get('sent') == 'true' or resp.status_code == 200:
            _logger.info('WhatsApp UltraMsg sent to %s', to)
            return True
        _logger.warning('WhatsApp UltraMsg error: %s', resp.text[:200])
        return False

    def _send_twilio(self, to, message):
        """Twilio WhatsApp: POST to Twilio Messages API"""
        endpoint   = 'https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json'
        account_sid = self._wa_param('twilio_sid', '')
        auth_token  = self._wa_param('token', '')
        from_number = self._wa_param('from_number', '')

        if not account_sid or not auth_token or not from_number:
            _logger.warning('WhatsApp Twilio: SID, token or from_number missing')
            return False

        payload = {
            'From': 'whatsapp:%s' % from_number,
            'To':   'whatsapp:%s' % to,
            'Body': message,
        }
        resp = requests.post(
            endpoint % account_sid,
            data=payload,
            auth=(account_sid, auth_token),
            timeout=15
        )
        if resp.status_code in (200, 201):
            _logger.info('WhatsApp Twilio sent to %s', to)
            return True
        _logger.warning('WhatsApp Twilio error %s: %s', resp.status_code, resp.text[:200])
        return False

    def _send_custom(self, to, message):
        """Generic HTTP provider: POST JSON {to, message, token}"""
        endpoint = self._wa_param('endpoint', '').rstrip('/')
        token    = self._wa_param('token', '')
        from_no  = self._wa_param('from_number', '')

        if not endpoint:
            _logger.warning('WhatsApp Custom: no endpoint configured')
            return False

        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer %s' % token

        payload = {'to': to, 'message': message, 'from': from_no, 'token': token}
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=15)
        if resp.status_code in (200, 201, 202):
            _logger.info('WhatsApp Custom sent to %s', to)
            return True
        _logger.warning('WhatsApp Custom error %s: %s', resp.status_code, resp.text[:200])
        return False

    # ── Convenience methods ───────────────────────────────────────────────

    def send_to_admin(self, message):
        """Send a WhatsApp message to the configured admin number."""
        admin_no = self._wa_param('admin_number', '')
        if admin_no:
            return self.send_whatsapp(admin_no, message)
        return False

    # ── Number normalization ──────────────────────────────────────────────

    @staticmethod
    def _normalize_number(number):
        """Ensure number is in +COUNTRYCODE format."""
        number = ''.join(c for c in (number or '') if c.isdigit() or c == '+')
        if number and not number.startswith('+'):
            number = '+' + number
        return number

    # ── Message templates ─────────────────────────────────────────────────

    def msg_new_request(self, req):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        return (
            u'\U0001F6A2 *New Shipment Request*\n'
            u'Ref: *{ref}*\n'
            u'From: {name} — {company}\n'
            u'Type: {ctype}\n'
            u'Goods: {goods}\n'
            u'\n\U0001F517 {url}/web#model=customs.portal.request'
        ).format(
            ref=req.name,
            name=req.requester_name,
            company=req.requester_company or '',
            ctype=dict(req._fields['clearance_type'].selection).get(req.clearance_type, req.clearance_type),
            goods=(req.goods_description or '')[:80],
            url=base_url,
        )

    def msg_approved(self, req):
        tracking_url = req._get_tracking_url()
        return (
            u'✅ *Request Approved — تمت الموافقة*\n'
            u'Dear {name},\n\n'
            u'Your shipment request *{ref}* has been approved.\n'
            u'A customs clearance order is now in progress.\n\n'
            u'\U0001F4CD Track your shipment:\n{url}'
        ).format(
            name=req.requester_name,
            ref=req.name,
            url=tracking_url,
        )

    def msg_rejected(self, req):
        return (
            u'❌ *Request Update — تحديث الطلب*\n'
            u'Dear {name},\n\n'
            u'Unfortunately your request *{ref}* could not be processed at this time.\n\n'
            u'Reason: {reason}\n\n'
            u'Please contact us for more details or submit a new request.'
        ).format(
            name=req.requester_name,
            ref=req.name,
            reason=req.rejection_reason or 'Please contact us for details.',
        )

    def msg_offer_sent(self, req):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        vat = round(req.estimated_service_fee * 0.15, 2)
        total = round(req.estimated_service_fee + vat + req.estimated_duty_amount, 2)
        accept_url = '%s/customs-portal/offer/accept/%s' % (base_url, req.offer_token)
        return (
            u'\U0001F4CB *Service Offer — عرض خدمات*\n'
            u'Dear {name},\n\n'
            u'We have prepared a service offer for your shipment *{ref}*.\n\n'
            u'\U0001F4B0 Service Fee: SAR {fee:.2f}\n'
            u'   + VAT (15%%): SAR {vat:.2f}\n'
            u'   Total: *SAR {total:.2f}*\n\n'
            u'✅ Accept offer:\n{accept}\n\n'
            u'Reply to this message or click the link to respond.'
        ).format(
            name=req.requester_name,
            ref=req.name,
            fee=req.estimated_service_fee,
            vat=vat,
            total=total,
            accept=accept_url,
        )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── WhatsApp settings fields (stored in ir.config_parameter) ──────────

    wa_enabled = fields.Boolean(
        string='Enable WhatsApp Notifications',
        config_parameter='customs.whatsapp.enabled',
    )
    wa_provider = fields.Selection([
        ('waha',     'WAHA (Self-Hosted)'),
        ('ultramsg', 'UltraMsg (Cloud)'),
        ('twilio',   'Twilio'),
        ('custom',   'Custom HTTP API'),
    ], string='Provider', config_parameter='customs.whatsapp.provider', default='waha')
    wa_endpoint = fields.Char(
        string='API Endpoint URL',
        config_parameter='customs.whatsapp.endpoint',
    )
    wa_token = fields.Char(
        string='API Token / Key',
        config_parameter='customs.whatsapp.token',
    )
    wa_from_number = fields.Char(
        string='Sender Number (e.g. +966501234567)',
        config_parameter='customs.whatsapp.from_number',
    )
    wa_admin_number = fields.Char(
        string='Admin WhatsApp Number',
        help='Receives alerts for every new portal request',
        config_parameter='customs.whatsapp.admin_number',
    )
    wa_twilio_sid = fields.Char(
        string='WA Twilio Account SID',
        config_parameter='customs.whatsapp.twilio_sid',
    )
    wa_waha_session = fields.Char(
        string='WAHA Session Name',
        config_parameter='customs.whatsapp.waha_session',
        default='default',
    )
    wa_notify_new = fields.Boolean(
        string='Notify admin on new request',
        config_parameter='customs.whatsapp.notify_new',
    )
    wa_notify_approve = fields.Boolean(
        string='Notify client on approval',
        config_parameter='customs.whatsapp.notify_approve',
    )
    wa_notify_reject = fields.Boolean(
        string='Notify client on rejection',
        config_parameter='customs.whatsapp.notify_reject',
    )
    wa_notify_offer = fields.Boolean(
        string='Notify client when offer is sent',
        config_parameter='customs.whatsapp.notify_offer',
    )

    def action_test_whatsapp(self):
        """Send a test WhatsApp message to the admin number."""
        self.ensure_one()
        self.execute()  # save first
        sender = self.env['customs.whatsapp.sender']
        admin_no = self.env['ir.config_parameter'].sudo().get_param('customs.whatsapp.admin_number', '')
        if not admin_no:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'No Admin Number', 'message': 'Please set an Admin WhatsApp Number first.', 'type': 'warning'},
            }
        ok = sender.send_whatsapp(admin_no, u'✅ WhatsApp test from Customs Clearance KSA system. Configuration is working!')
        if ok:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Test Sent!', 'message': 'WhatsApp test message sent to %s' % admin_no, 'type': 'success'},
            }
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': 'Send Failed', 'message': 'Could not send test message. Check logs and configuration.', 'type': 'danger', 'sticky': True},
        }
