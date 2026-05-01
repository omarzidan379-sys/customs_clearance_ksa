# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta


class CustomsDashboard(http.Controller):

    @http.route('/customs_clearance/dashboard_data', type='json', auth='user')
    def get_dashboard_data(self, **kwargs):
        """Comprehensive dashboard: shipments + ZATCA + invoicing + profitability."""
        try:
            Clearance = request.env['customs.clearance']
            Shipment  = request.env['customs.shipment']
            Invoice   = request.env['customs.service.invoice']

            today       = datetime.now().date()
            month_start = today.replace(day=1)

            # ── 1. Shipment KPIs ─────────────────────────────────────────────
            total_shipments = Shipment.search_count([('state', '!=', 'delivered')])
            in_customs      = Clearance.search_count([
                ('state', 'in', ['submitted', 'customs_review', 'inspection'])
            ])
            delayed         = Clearance.search_count([
                ('priority', '=', '2'), ('state', '!=', 'delivered')
            ])
            cleared_today   = Clearance.search_count([
                ('actual_clearance_date', '=', today)
            ])

            # ── 2. Revenue from service invoices ──────────────────────────────
            paid_invoices_month = Invoice.search([
                ('invoice_date', '>=', month_start),
                ('state', '=', 'paid'),
            ])
            monthly_revenue = sum(paid_invoices_month.mapped('total'))

            # Monthly revenue from all (confirmed+) for broader view
            all_invoices_month = Invoice.search([
                ('invoice_date', '>=', month_start),
                ('state', 'in', ['confirmed', 'sent', 'paid']),
            ])
            monthly_revenue_all = sum(all_invoices_month.mapped('total'))
            currency = request.env.company.currency_id.symbol

            # ── 3. ZATCA KPIs ─────────────────────────────────────────────────
            zatca_cleared  = Invoice.search_count([('zatca_status', '=', 'cleared')])
            zatca_pending  = Invoice.search_count([('zatca_status', '=', 'pending')])
            zatca_error    = Invoice.search_count([('zatca_status', '=', 'error')])
            zatca_submitted = Invoice.search_count([('zatca_status', '=', 'submitted')])

            # ── 4. Pending Invoices ───────────────────────────────────────────
            pending_invoices = Invoice.search([
                ('state', 'in', ['confirmed', 'sent']),
                ('amount_due', '>', 0),
            ])
            pending_inv_count  = len(pending_invoices)
            pending_inv_amount = sum(pending_invoices.mapped('amount_due'))

            # ── 5. Profitability (monthly revenue vs estimated cost) ──────────
            # Revenue = sum of confirmed+ invoice totals this month
            # Cost estimate = sum of clearance total_duty_amount + port_charges + demurrage
            # (Vendor bills are in account.move; use clearance fields as proxy)
            clearances_month = Clearance.search([
                ('date', '>=', month_start),
                ('state', '!=', 'cancelled'),
            ])
            monthly_cost = sum(
                (c.total_duty_amount or 0) + (c.port_charges or 0) + (c.demurrage_fee or 0)
                for c in clearances_month
            )
            monthly_profit = monthly_revenue_all - monthly_cost

            # ── 6. Outstanding receivables ────────────────────────────────────
            outstanding_invoices = Invoice.search([
                ('state', 'in', ['confirmed', 'sent', 'paid']),
                ('amount_due', '>', 0),
            ])
            outstanding_total = sum(outstanding_invoices.mapped('amount_due'))

            # ── 7. Status chart ───────────────────────────────────────────────
            states = Clearance._fields['state'].selection
            status_labels, status_values = [], []
            for code, label in states:
                count = Clearance.search_count([('state', '=', code)])
                if count > 0:
                    status_labels.append(label.split(' / ')[0])
                    status_values.append(count)

            # ── 8. Monthly trend (last 6 months, real data) ───────────────────
            monthly_labels, monthly_revenue_trend, monthly_profit_trend = [], [], []
            for offset in range(5, -1, -1):
                # Compute start/end of each month
                y, m = today.year, today.month - offset
                while m <= 0:
                    m += 12; y -= 1
                import calendar
                _, last_day = calendar.monthrange(y, m)
                from datetime import date
                mstart = date(y, m, 1)
                mend   = date(y, m, last_day)
                lbl    = mstart.strftime('%b %Y')
                monthly_labels.append(lbl)

                inv_month = Invoice.search([
                    ('invoice_date', '>=', mstart),
                    ('invoice_date', '<=', mend),
                    ('state', 'in', ['confirmed', 'sent', 'paid']),
                ])
                rev  = sum(inv_month.mapped('total'))
                clrs = Clearance.search([
                    ('date', '>=', mstart),
                    ('date', '<=', mend),
                    ('state', '!=', 'cancelled'),
                ])
                cost = sum(
                    (c.total_duty_amount or 0) + (c.port_charges or 0) + (c.demurrage_fee or 0)
                    for c in clrs
                )
                monthly_revenue_trend.append(round(rev, 2))
                monthly_profit_trend.append(round(rev - cost, 2))

            # ── 9. Recent clearances ──────────────────────────────────────────
            progress_map = {
                'draft': 5, 'acd_submitted': 15, 'submitted': 30,
                'customs_review': 45, 'inspection': 60,
                'duty_payment': 75, 'released': 90, 'delivered': 100, 'cancelled': 0,
            }
            recent_clearances = []
            for rec in Clearance.search([], limit=12, order='write_date desc'):
                recent_clearances.append({
                    'id':           rec.id,
                    'name':         rec.name,
                    'partner_name': rec.partner_id.name if rec.partner_id else 'N/A',
                    'type':         rec.clearance_type,
                    'date':         rec.date.strftime('%Y-%m-%d') if rec.date else '',
                    'state':        rec.state,
                    'state_label':  dict(states).get(rec.state, '').split(' / ')[0],
                    'progress':     progress_map.get(rec.state, 0),
                    'lane':         getattr(rec, 'inspection_lane', ''),
                })

            # ── 10. Recent ZATCA invoices ─────────────────────────────────────
            recent_invoices = []
            for inv in Invoice.search([], limit=8, order='invoice_date desc'):
                recent_invoices.append({
                    'id':            inv.id,
                    'name':          inv.name,
                    'partner':       inv.partner_id.name if inv.partner_id else '',
                    'total':         round(inv.total, 2),
                    'currency':      currency,
                    'state':         inv.state,
                    'zatca_status':  inv.zatca_status,
                    'date':          str(inv.invoice_date or ''),
                    'fatoorah_no':   inv.fatoorah_invoice_no or '',
                })

            return {
                'stats': {
                    'total_shipments':   total_shipments,
                    'in_customs':        in_customs,
                    'delayed':           delayed,
                    'cleared_today':     cleared_today,
                    'monthly_revenue':   f'{monthly_revenue_all:,.2f}',
                    'monthly_cost':      f'{monthly_cost:,.2f}',
                    'monthly_profit':    f'{monthly_profit:,.2f}',
                    'outstanding':       f'{outstanding_total:,.2f}',
                    'zatca_cleared':     zatca_cleared,
                    'zatca_pending':     zatca_pending,
                    'zatca_submitted':   zatca_submitted,
                    'zatca_error':       zatca_error,
                    'pending_invoices':  pending_inv_count,
                    'pending_amount':    f'{pending_inv_amount:,.2f}',
                    'currency':          currency,
                },
                'chart_data': {
                    'status': {
                        'labels': status_labels,
                        'values': status_values,
                    },
                    'monthly': {
                        'labels':  monthly_labels,
                        'revenue': monthly_revenue_trend,
                        'profit':  monthly_profit_trend,
                    },
                },
                'recent_clearances': recent_clearances,
                'recent_invoices':   recent_invoices,
            }

        except Exception as e:
            sym = request.env.company.currency_id.symbol if request.env.company else 'SAR'
            return {
                'stats': {
                    'total_shipments': 0, 'in_customs': 0, 'delayed': 0,
                    'cleared_today': 0, 'monthly_revenue': '0.00',
                    'monthly_cost': '0.00', 'monthly_profit': '0.00',
                    'outstanding': '0.00', 'zatca_cleared': 0, 'zatca_pending': 0,
                    'zatca_submitted': 0, 'zatca_error': 0,
                    'pending_invoices': 0, 'pending_amount': '0.00', 'currency': sym,
                },
                'chart_data': {
                    'status': {'labels': [], 'values': []},
                    'monthly': {
                        'labels': [], 'revenue': [], 'profit': [],
                    },
                },
                'recent_clearances': [],
                'recent_invoices':   [],
                'error': str(e),
            }
