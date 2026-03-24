/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

export class CustomsDashboard extends Component {
    setup() {
        this.action = useService("action");
        this.rpc = useService("rpc");
        this.statusChartRef = useRef("statusChart");
        this.chartInstance = null;

        this.state = useState({
            stats: {},
            recent_clearances: [],
            chart_data: {
                status: [],
                monthly: []
            },
            selectedFilter: 'all',
            loading: true,
            showConfetti: false
        });

        onWillStart(async () => {
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js");
            await this.loadDashboardData();
        });

        onMounted(() => {
            this.renderStatusChart();
            // Trigger animations
            setTimeout(() => {
                this.state.loading = false;
                this.animateCards();
            }, 500);
        });
    }

    async loadDashboardData() {
        const data = await this.rpc("/customs_clearance/dashboard_data", {});
        this.state.stats = data.stats;
        this.state.recent_clearances = data.recent_clearances;
        this.state.chart_data = data.chart_data;
    }

    animateCards() {
        const cards = document.querySelectorAll('.kpi-card');
        cards.forEach((card, index) => {
            setTimeout(() => {
                card.classList.add('animate-in');
            }, index * 100);
        });
    }

    renderStatusChart() {
        const ctx = this.statusChartRef.el;
        
        // Egyptian/Saudi/UAE inspired colors
        const colors = [
            '#CE1126', // Egypt Red
            '#165B33', // Saudi Green
            '#00732F', // UAE Green
            '#C09300', // Gold
            '#FF0000', // UAE Red
            '#FFD700', // Saudi Gold
            '#3498db', // Blue
            '#9b59b6'  // Purple
        ];
        
        this.chartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: this.state.chart_data.status.labels,
                datasets: [{
                    data: this.state.chart_data.status.values,
                    backgroundColor: colors,
                    borderWidth: 3,
                    borderColor: '#fff',
                    hoverOffset: 15,
                    hoverBorderWidth: 4,
                    hoverBorderColor: '#C09300'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 1.5,
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 2000,
                    easing: 'easeInOutQuart'
                },
                plugins: {
                    legend: { 
                        position: 'bottom', 
                        labels: { 
                            usePointStyle: true, 
                            padding: 12,
                            font: { 
                                size: 11,
                                family: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
                            },
                            generateLabels: (chart) => {
                                const data = chart.data;
                                return data.labels.map((label, i) => ({
                                    text: `${label} (${data.datasets[0].data[i]})`,
                                    fillStyle: data.datasets[0].backgroundColor[i],
                                    hidden: false,
                                    index: i
                                }));
                            }
                        },
                        onClick: (e, legendItem, legend) => {
                            this.onChartLegendClick(this.state.chart_data.status.labels[legendItem.index]);
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#C09300',
                        bodyColor: '#fff',
                        borderColor: '#C09300',
                        borderWidth: 2,
                        padding: 12,
                        displayColors: true,
                        callbacks: {
                            label: (context) => {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '65%',
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const label = this.state.chart_data.status.labels[index];
                        this.onChartSegmentClick(label);
                    }
                }
            }
        });
    }

    // KPI Card Click Handlers
    onKpiClick(type) {
        let domain = [];
        let viewMode = 'list,form';
        
        switch(type) {
            case 'total_shipments':
                domain = [['state', '!=', 'delivered']];
                this.openAction('customs.shipment', 'Active Shipments / الشحنات النشطة', domain, viewMode);
                break;
            case 'in_customs':
                domain = [['state', 'in', ['submitted', 'customs_review', 'inspection']]];
                this.openAction('customs.clearance', 'In Customs Review / قيد المراجعة', domain, viewMode);
                break;
            case 'delayed':
                domain = [['priority', '=', '2'], ['state', '!=', 'delivered']];
                this.openAction('customs.clearance', 'Urgent Clearances / عاجل', domain, viewMode);
                break;
            case 'cleared_today':
                const today = new Date().toISOString().split('T')[0];
                domain = [['actual_clearance_date', '=', today]];
                this.openAction('customs.clearance', 'Cleared Today / المُفرج عنها اليوم', domain, viewMode);
                break;
            case 'revenue':
                const monthStart = new Date();
                monthStart.setDate(1);
                domain = [
                    ['date', '>=', monthStart.toISOString().split('T')[0]], 
                    ['state', '!=', 'cancelled']
                ];
                this.openAction('customs.clearance', 'Monthly Revenue / الإيرادات الشهرية', domain, viewMode);
                break;
        }
    }

    // Chart Segment Click Handler
    onChartSegmentClick(statusLabel) {
        const stateMap = {
            'Draft': 'draft',
            'مسودة': 'draft',
            'Bill of Entry': 'bill_entry',
            'تقديم البيان': 'bill_entry',
            'Classification': 'classification',
            'التصنيف': 'classification',
            'Valuation': 'valuation',
            'التقييم': 'valuation',
            'Submitted': 'submitted',
            'مقدمة': 'submitted',
            'Customs Review': 'customs_review',
            'مراجعة جمركية': 'customs_review',
            'Inspection': 'inspection',
            'فحص': 'inspection',
            'Duty Calculation': 'duty_calculation',
            'حساب الرسوم': 'duty_calculation',
            'Duty Payment': 'duty_payment',
            'سداد': 'duty_payment',
            'Released': 'released',
            'إفراج': 'released',
            'Delivered': 'delivered',
            'مُسلَّم': 'delivered',
            'Cancelled': 'cancelled',
            'ملغي': 'cancelled'
        };
        
        const stateCode = stateMap[statusLabel] || statusLabel.toLowerCase().replace(' ', '_');
        const domain = [['state', '=', stateCode]];
        this.openAction('customs.clearance', `${statusLabel}`, domain, 'list,form');
    }

    // Chart Legend Click Handler
    onChartLegendClick(statusLabel) {
        this.onChartSegmentClick(statusLabel);
    }

    // Refresh Dashboard with Animation
    async refreshDashboard() {
        this.state.loading = true;
        const refreshBtn = document.querySelector('.btn-refresh');
        if (refreshBtn) {
            refreshBtn.classList.add('rotating');
        }
        
        await this.loadDashboardData();
        
        if (this.chartInstance) {
            this.chartInstance.data.labels = this.state.chart_data.status.labels;
            this.chartInstance.data.datasets[0].data = this.state.chart_data.status.values;
            this.chartInstance.update('active');
        }
        
        setTimeout(() => {
            this.state.loading = false;
            if (refreshBtn) {
                refreshBtn.classList.remove('rotating');
            }
            this.animateCards();
        }, 800);
    }

    // Open Action Helper
    openAction(model, name, domain, viewMode) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: name,
            res_model: model,
            views: viewMode.split(',').map(v => [false, v.trim()]),
            domain: domain,
            target: 'current',
        });
    }

    // Open Clearance Record
    openClearance(id) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'customs.clearance',
            res_id: id,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    // Get Status Class for Badges
    getStatusClass(state) {
        const statusMap = {
            'draft': 'draft',
            'bill_entry': 'pending',
            'classification': 'pending',
            'valuation': 'pending',
            'submitted': 'transit',
            'customs_review': 'transit',
            'inspection': 'pending',
            'duty_calculation': 'pending',
            'duty_payment': 'pending',
            'released': 'cleared',
            'delivered': 'cleared',
            'cancelled': 'problem'
        };
        return statusMap[state] || 'transit';
    }

    // Filter Clearances
    filterClearances(filterType) {
        this.state.selectedFilter = filterType;
    }

    // Create New Clearance with Animation
    createNewClearance() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'New Clearance / تخليص جديد',
            res_model: 'customs.clearance',
            views: [[false, 'form']],
            target: 'current',
            context: { default_state: 'draft' }
        });
    }
}

CustomsDashboard.template = "customs_clearance_ksa.Dashboard";
registry.category("actions").add("customs_clearance_ksa.dashboard", CustomsDashboard);
