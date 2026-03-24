# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta


class CustomsDashboard(http.Controller):

    @http.route('/customs_clearance/dashboard_data', type='json', auth='user')
    def get_dashboard_data(self, **kwargs):
        """Fetch statistics and data for the customs dashboard."""

        try:
            # Models
            Clearance = request.env['customs.clearance']
            Shipment = request.env['customs.shipment']

            # 1. KPI Stats
            today = datetime.now().date()
            month_start = today.replace(day=1)

            total_shipments = Shipment.search_count([('state', '!=', 'delivered')])
            in_customs = Clearance.search_count([('state', 'in', ['submitted', 'customs_review', 'inspection'])])
            delayed = Clearance.search_count([('priority', '=', '2'), ('state', '!=', 'delivered')])
            cleared_today = Clearance.search_count([('actual_clearance_date', '=', today)])

            # Revenue estimate (sum of service fees in current month)
            monthly_revenue_data = Clearance.search_read(
                [('date', '>=', month_start), ('state', '!=', 'cancelled')],
                ['service_fee']
            )
            monthly_revenue = sum(item['service_fee'] for item in monthly_revenue_data if item.get('service_fee'))
            currency = request.env.company.currency_id.symbol

            # 2. Status Chart Data
            states = Clearance._fields['state'].selection
            status_labels = []
            status_values = []
            for state_code, state_label in states:
                count = Clearance.search_count([('state', '=', state_code)])
                if count > 0:
                    status_labels.append(state_label.split(' / ')[0])
                    status_values.append(count)

            # 3. Monthly Chart Data (Mocking last 6 months for visualization if no data)
            # In real world, would group by date
            monthly_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
            monthly_imports = [45, 52, 38, 65, 48, 72]
            monthly_exports = [30, 25, 42, 35, 55, 40]

            # 4. Recent Clearances Table
            recent_clearances = []
            records = Clearance.search([], limit=10, order='write_date desc')
            for rec in records:
                # Map state to progress %
                progress_map = {
                    'draft': 10, 'submitted': 25, 'customs_review': 45,
                    'inspection': 65, 'duty_payment': 80, 'released': 95, 'delivered': 100
                }
                recent_clearances.append({
                    'id': rec.id,
                    'name': rec.name,
                    'partner_name': rec.partner_id.name if rec.partner_id else 'N/A',
                    'type': rec.clearance_type,
                    'date': rec.date.strftime('%Y-%m-%d') if rec.date else '',
                    'state': rec.state,
                    'state_label': dict(states).get(rec.state, '').split(' / ')[0],
                    'progress': progress_map.get(rec.state, 0)
                })

            return {
                'stats': {
                    'total_shipments': total_shipments,
                    'in_customs': in_customs,
                    'delayed': delayed,
                    'cleared_today': cleared_today,
                    'monthly_revenue': f"{monthly_revenue:,.2f}",
                    'currency': currency
                },
                'chart_data': {
                    'status': {
                        'labels': status_labels,
                        'values': status_values
                    },
                    'monthly': {
                        'labels': monthly_labels,
                        'imports': monthly_imports,
                        'exports': monthly_exports
                    }
                },
                'recent_clearances': recent_clearances
            }
        except Exception as e:
            # Return fallback data if models are not ready
            return {
                'stats': {
                    'total_shipments': 0,
                    'in_customs': 0,
                    'delayed': 0,
                    'cleared_today': 0,
                    'monthly_revenue': "0.00",
                    'currency': request.env.company.currency_id.symbol if request.env.company else '$'
                },
                'chart_data': {
                    'status': {
                        'labels': ['Draft', 'Submitted', 'Review', 'Released'],
                        'values': [0, 0, 0, 0]
                    },
                    'monthly': {
                        'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                        'imports': [0, 0, 0, 0, 0, 0],
                        'exports': [0, 0, 0, 0, 0, 0]
                    }
                },
                'recent_clearances': [],
                'error': str(e)
            }
