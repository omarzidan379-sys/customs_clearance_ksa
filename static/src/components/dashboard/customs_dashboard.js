/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, useState, useRef, onWillUnmount } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

export class CustomsDashboard extends Component {
    setup() {
        this.action          = useService("action");
        this.rpc             = useService("rpc");
        this.statusChartRef  = useRef("statusChart");
        this.revenueChartRef = useRef("revenueChart");
        this.globeCanvasRef  = useRef("globeCanvas");

        this.chartStatus  = null;
        this.chartRevenue = null;
        this._clockInterval = null;
        this._globeAnimId   = null;
        this._scrollParents = [];

        this.state = useState({
            stats:             {},
            recent_clearances: [],
            recent_invoices:   [],
            chart_data:        { status: { labels: [], values: [] }, monthly: { labels: [], revenue: [], profit: [] } },
            selectedFilter:    'all',
            loading:           true,
            currentTime:       '',
        });

        onWillStart(async () => {
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js");
            await this.loadDashboardData();
        });

        onMounted(() => {
            this._unlockScroll();
            this.renderStatusChart();
            this.renderRevenueChart();
            this.initGlobe();
            this._clockInterval = setInterval(() => {
                const now = new Date();
                this.state.currentTime = now.toLocaleTimeString('en-GB', {
                    hour: '2-digit', minute: '2-digit', second: '2-digit',
                    hour12: false, timeZone: 'Asia/Riyadh',
                });
            }, 1000);
            setTimeout(() => {
                this.state.loading = false;
                this.animateCards();
                this.animateCounters();
            }, 500);
        });

        onWillUnmount(() => {
            if (this._clockInterval) clearInterval(this._clockInterval);
            if (this._globeAnimId)   cancelAnimationFrame(this._globeAnimId);
            if (this.chartStatus)    this.chartStatus.destroy();
            if (this.chartRevenue)   this.chartRevenue.destroy();
            this._restoreScroll();
        });
    }

    // ── Scroll unlock: force Odoo's parent containers to allow scrolling ──
    _unlockScroll() {
        const selectors = [
            '.o_action_manager',
            '.o_action',
            '.o_view_controller',
            '.o_content',
            '.o_main_content',
        ];
        this._scrollParents = [];
        selectors.forEach(sel => {
            const el = document.querySelector(sel);
            if (el) {
                this._scrollParents.push({ el, prev: { overflow: el.style.overflow, overflowY: el.style.overflowY, height: el.style.height } });
                el.style.overflow  = 'visible';
                el.style.overflowY = 'visible';
                if (sel === '.o_content') {
                    el.style.overflow  = 'auto';
                    el.style.overflowY = 'auto';
                }
            }
        });
    }

    _restoreScroll() {
        this._scrollParents.forEach(({ el, prev }) => {
            el.style.overflow  = prev.overflow;
            el.style.overflowY = prev.overflowY;
            el.style.height    = prev.height;
        });
        this._scrollParents = [];
    }

    async loadDashboardData() {
        const data = await this.rpc("/customs_clearance/dashboard_data", {});
        this.state.stats             = data.stats   || {};
        this.state.recent_clearances = data.recent_clearances || [];
        this.state.recent_invoices   = data.recent_invoices   || [];
        this.state.chart_data        = data.chart_data || { status: { labels: [], values: [] }, monthly: { labels: [], revenue: [], profit: [] } };
    }

    // ── Animated counters ────────────────────────────────────────────────────
    animateCounters() {
        document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
            const target = parseInt(el.dataset.target, 10);
            if (isNaN(target) || target === 0) return;
            const start = performance.now();
            const tick = (now) => {
                const p = Math.min((now - start) / 1400, 1);
                el.textContent = Math.floor((1 - Math.pow(1 - p, 3)) * target).toLocaleString();
                if (p < 1) requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
        });
    }

    animateCards() {
        document.querySelectorAll('.kpi-card').forEach((card, i) => {
            setTimeout(() => card.classList.add('animate-in'), i * 80);
        });
    }

    get filteredClearances() {
        const items = this.state.recent_clearances;
        if (this.state.selectedFilter === 'all') return items;
        const groups = {
            pending: ['draft', 'acd_submitted', 'submitted', 'customs_review', 'inspection', 'duty_payment'],
            cleared: ['released', 'delivered'],
        };
        return items.filter(r => (groups[this.state.selectedFilter] || []).includes(r.state));
    }

    // ── Status Doughnut Chart ────────────────────────────────────────────────
    renderStatusChart() {
        const ctx = this.statusChartRef.el;
        if (!ctx) return;
        if (this.chartStatus) this.chartStatus.destroy();

        const colors = ['#6366f1','#00d4aa','#f43f5e','#eab308','#8b5cf6','#22c55e','#3b82f6','#f97316','#ec4899'];
        const centerPlugin = {
            id: 'centerText',
            beforeDraw(chart) {
                const { width, height, ctx: c } = chart;
                const total = chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                c.save();
                c.font = 'bold 30px "Segoe UI"';
                c.fillStyle = '#e2e8f0';
                c.textAlign = 'center'; c.textBaseline = 'middle';
                c.fillText(total, width / 2, height / 2 - 10);
                c.font = '600 11px "Segoe UI"';
                c.fillStyle = '#64748b';
                c.fillText('TOTAL', width / 2, height / 2 + 14);
                c.restore();
            }
        };

        this.chartStatus = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: this.state.chart_data.status.labels,
                datasets: [{ data: this.state.chart_data.status.values, backgroundColor: colors, borderWidth: 2, borderColor: '#0f172a', hoverOffset: 12 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: { animateRotate: true, animateScale: true, duration: 2000, easing: 'easeInOutQuart' },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { usePointStyle: true, padding: 14, color: '#e2e8f0', font: { size: 10, weight: '600' },
                            generateLabels: (c) => c.data.labels.map((l, i) => ({
                                text: `${l} (${c.data.datasets[0].data[i]})`,
                                fillStyle: c.data.datasets[0].backgroundColor[i], hidden: false, index: i
                            }))
                        },
                        onClick: (_, item) => this.onChartLegendClick(this.state.chart_data.status.labels[item.index])
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15,23,42,0.95)', titleColor: '#818cf8', bodyColor: '#e2e8f0',
                        borderColor: 'rgba(99,102,241,0.3)', borderWidth: 1, padding: 12,
                        callbacks: { label: (c) => { const t = c.dataset.data.reduce((a,b)=>a+b,0); return `${c.label}: ${c.parsed} (${((c.parsed/t)*100).toFixed(1)}%)`; } }
                    }
                },
                cutout: '65%',
                onClick: (_, els) => { if (els.length) this.onChartSegmentClick(this.state.chart_data.status.labels[els[0].index]); }
            },
            plugins: [centerPlugin]
        });
    }

    // ── Revenue / Profit Line Chart ──────────────────────────────────────────
    renderRevenueChart() {
        const ctx = this.revenueChartRef.el;
        if (!ctx) return;
        if (this.chartRevenue) this.chartRevenue.destroy();

        const md = this.state.chart_data.monthly;
        this.chartRevenue = new Chart(ctx, {
            type: 'line',
            data: {
                labels: md.labels || [],
                datasets: [
                    {
                        label: 'Revenue (SAR)',
                        data:  md.revenue || [],
                        borderColor: '#06b6d4', backgroundColor: 'rgba(6,182,212,0.1)',
                        borderWidth: 2.5, fill: true, tension: 0.4,
                        pointBackgroundColor: '#06b6d4', pointRadius: 4, pointHoverRadius: 7,
                    },
                    {
                        label: 'Net Profit (SAR)',
                        data:  md.profit || [],
                        borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.08)',
                        borderWidth: 2.5, fill: true, tension: 0.4,
                        pointBackgroundColor: '#22c55e', pointRadius: 4, pointHoverRadius: 7,
                    },
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: { duration: 1800, easing: 'easeInOutQuart' },
                plugins: {
                    legend: { labels: { color: '#e2e8f0', font: { size: 11, weight: '600' }, usePointStyle: true, padding: 16 } },
                    tooltip: {
                        backgroundColor: 'rgba(15,23,42,0.95)', titleColor: '#06b6d4',
                        bodyColor: '#e2e8f0', borderColor: 'rgba(6,182,212,0.3)', borderWidth: 1, padding: 12,
                    }
                },
                scales: {
                    x: { grid: { color: 'rgba(99,102,241,0.08)' }, ticks: { color: '#64748b', font: { size: 10 } } },
                    y: { grid: { color: 'rgba(99,102,241,0.08)' }, ticks: { color: '#64748b', font: { size: 10 },
                        callback: (v) => v >= 1000 ? `${(v/1000).toFixed(0)}K` : v } }
                }
            }
        });
    }

    // ── 3D Globe ─────────────────────────────────────────────────────────────
    initGlobe() {
        const canvas = this.globeCanvasRef.el;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        let w, h, cx, cy, R, rotation = 0, mouseX = 0.5, mouseY = 0.5;

        const ports = [
            { name: 'Jeddah',    lat: 21.5, lon: 39.2,  color: '#00ffcc' },
            { name: 'Dammam',    lat: 26.4, lon: 50.1,  color: '#00ffcc' },
            { name: 'Dubai',     lat: 25.3, lon: 55.3,  color: '#eab308' },
            { name: 'Shanghai',  lat: 31.2, lon: 121.5, color: '#f43f5e' },
            { name: 'Rotterdam', lat: 51.9, lon: 4.5,   color: '#6366f1' },
            { name: 'Mumbai',    lat: 19.1, lon: 72.9,  color: '#8b5cf6' },
            { name: 'Singapore', lat: 1.3,  lon: 103.8, color: '#f97316' },
            { name: 'Hamburg',   lat: 53.5, lon: 10.0,  color: '#3b82f6' },
        ];
        const routes = [[0,3],[0,4],[1,5],[1,6],[0,7],[3,6],[4,7],[5,6]];
        const toRad = d => d * Math.PI / 180;

        const project = (lat, lon) => {
            const phi = toRad(90 - lat), theta = toRad(lon + rotation);
            const x = R * Math.sin(phi) * Math.cos(theta);
            const y = R * Math.cos(phi);
            const z = R * Math.sin(phi) * Math.sin(theta);
            return { x: cx + x + (mouseX - 0.5) * 18, y: cy - y + (mouseY - 0.5) * 18, z };
        };

        const resize = () => {
            const dpr = window.devicePixelRatio || 1;
            w = window.innerWidth; h = window.innerHeight;
            canvas.width = w * dpr; canvas.height = h * dpr;
            canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            cx = w / 2; cy = h / 2; R = Math.min(w, h) * 0.33;
        };

        const drawGlobe = (t) => {
            ctx.clearRect(0, 0, w, h);
            for (let lat = -60; lat <= 60; lat += 30) {
                ctx.beginPath(); ctx.strokeStyle = 'rgba(99,102,241,0.15)'; ctx.lineWidth = 0.5;
                let s = false;
                for (let lon = 0; lon <= 360; lon += 3) {
                    const p = project(lat, lon);
                    if (p.z > 0) { if (!s) { ctx.moveTo(p.x, p.y); s = true; } else ctx.lineTo(p.x, p.y); } else s = false;
                }
                ctx.stroke();
            }
            for (let lon = 0; lon < 360; lon += 30) {
                ctx.beginPath(); ctx.strokeStyle = 'rgba(99,102,241,0.1)'; ctx.lineWidth = 0.5;
                let s = false;
                for (let lat = -90; lat <= 90; lat += 3) {
                    const p = project(lat, lon);
                    if (p.z > 0) { if (!s) { ctx.moveTo(p.x, p.y); s = true; } else ctx.lineTo(p.x, p.y); } else s = false;
                }
                ctx.stroke();
            }
            routes.forEach(([a, b]) => {
                const pA = ports[a], pB = ports[b];
                ctx.beginPath(); ctx.strokeStyle = 'rgba(99,102,241,0.35)'; ctx.lineWidth = 1.2;
                let s = false;
                for (let i = 0; i <= 40; i++) {
                    const f = i / 40;
                    const p = project(pA.lat + (pB.lat - pA.lat) * f, pA.lon + (pB.lon - pA.lon) * f);
                    if (p.z > 0) { if (!s) { ctx.moveTo(p.x, p.y); s = true; } else ctx.lineTo(p.x, p.y); } else s = false;
                }
                ctx.stroke();
                const f2 = (t * 0.0003 + a * 0.15) % 1;
                const dp = project(pA.lat + (pB.lat - pA.lat) * f2, pA.lon + (pB.lon - pA.lon) * f2);
                if (dp.z > 0) {
                    ctx.beginPath(); ctx.arc(dp.x, dp.y, 3, 0, Math.PI * 2);
                    ctx.fillStyle = '#818cf8'; ctx.fill();
                }
            });
            ports.forEach((port, i) => {
                const p = project(port.lat, port.lon);
                if (p.z > 0) {
                    const pulse = 1 + Math.sin(t * 0.003 + i) * 0.35;
                    const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 16 * pulse);
                    grd.addColorStop(0, port.color + '70'); grd.addColorStop(1, port.color + '00');
                    ctx.beginPath(); ctx.arc(p.x, p.y, 16 * pulse, 0, Math.PI * 2);
                    ctx.fillStyle = grd; ctx.fill();
                    ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
                    ctx.fillStyle = port.color; ctx.shadowColor = port.color; ctx.shadowBlur = 10; ctx.fill();
                    ctx.shadowBlur = 0;
                }
            });
        };

        const animate = (t) => {
            rotation += 0.12;
            drawGlobe(t);
            this._globeAnimId = requestAnimationFrame(animate.bind(this));
        };

        const dashEl = canvas.closest('.o_customs_dashboard');
        if (dashEl) {
            dashEl.addEventListener('mousemove', (e) => {
                mouseX = e.clientX / window.innerWidth;
                mouseY = e.clientY / window.innerHeight;
            });
        }
        resize();
        window.addEventListener('resize', resize);
        this._globeAnimId = requestAnimationFrame(animate.bind(this));
    }

    // ── KPI Click Handlers ───────────────────────────────────────────────────
    onKpiClick(type) {
        switch (type) {
            case 'total_shipments':
                this.openAction('customs.shipment', 'Active Shipments', [['state', '!=', 'delivered']], 'list,form'); break;
            case 'in_customs':
                this.openAction('customs.clearance', 'In Customs', [['state', 'in', ['submitted', 'customs_review', 'inspection']]], 'list,form'); break;
            case 'delayed':
                this.openAction('customs.clearance', 'Urgent', [['priority', '=', '2'], ['state', '!=', 'delivered']], 'list,form'); break;
            case 'cleared_today': {
                const t = new Date().toISOString().split('T')[0];
                this.openAction('customs.clearance', 'Cleared Today', [['actual_clearance_date', '=', t]], 'list,form'); break;
            }
            case 'revenue':
            case 'net_profit':
                this.openAction('customs.service.invoice', 'Service Invoices', [['state', 'in', ['confirmed', 'sent', 'paid']]], 'list,form'); break;
            case 'pending_invoices':
                this.openAction('customs.service.invoice', 'Pending Invoices', [['state', 'in', ['confirmed', 'sent']], ['amount_due', '>', 0]], 'list,form'); break;
            case 'zatca_cleared':
                this.openAction('customs.service.invoice', 'ZATCA Cleared', [['zatca_status', '=', 'cleared']], 'list,form'); break;
            case 'zatca_pending':
                this.openAction('customs.service.invoice', 'ZATCA Pending', [['zatca_status', '=', 'pending']], 'list,form'); break;
        }
    }

    onChartSegmentClick(label) {
        const map = {
            'Draft': 'draft', 'ACD Submitted': 'acd_submitted', 'Submitted to FASAH': 'submitted',
            'Customs Review': 'customs_review', 'Under Inspection': 'inspection',
            'Duty Payment': 'duty_payment', 'Released': 'released', 'Delivered': 'delivered', 'Cancelled': 'cancelled',
        };
        this.openAction('customs.clearance', label, [['state', '=', map[label] || label.toLowerCase().replace(/ /g, '_')]], 'list,form');
    }

    onChartLegendClick(label) { this.onChartSegmentClick(label); }

    async refreshDashboard() {
        this.state.loading = true;
        const btn = document.querySelector('.btn-refresh');
        if (btn) btn.classList.add('rotating');
        await this.loadDashboardData();
        if (this.chartStatus) {
            this.chartStatus.data.labels   = this.state.chart_data.status.labels;
            this.chartStatus.data.datasets[0].data = this.state.chart_data.status.values;
            this.chartStatus.update('active');
        }
        if (this.chartRevenue) {
            const md = this.state.chart_data.monthly;
            this.chartRevenue.data.labels = md.labels;
            this.chartRevenue.data.datasets[0].data = md.revenue;
            this.chartRevenue.data.datasets[1].data = md.profit;
            this.chartRevenue.update('active');
        }
        setTimeout(() => {
            this.state.loading = false;
            if (btn) btn.classList.remove('rotating');
            this.animateCards();
            this.animateCounters();
        }, 600);
    }

    openAction(model, name, domain, viewMode) {
        this.action.doAction({
            type: 'ir.actions.act_window', name, res_model: model,
            views: viewMode.split(',').map(v => [false, v.trim()]),
            domain, target: 'current',
        });
    }

    openClearance(id) {
        this.action.doAction({ type: 'ir.actions.act_window', res_model: 'customs.clearance', res_id: id, views: [[false, 'form']], target: 'current' });
    }

    openInvoice(id) {
        this.action.doAction({ type: 'ir.actions.act_window', res_model: 'customs.service.invoice', res_id: id, views: [[false, 'form']], target: 'current' });
    }

    getStatusClass(state) { return state || 'draft'; }
    filterClearances(type) { this.state.selectedFilter = type; }

    createNewClearance() {
        this.action.doAction({
            type: 'ir.actions.act_window', name: 'New Clearance', res_model: 'customs.clearance',
            views: [[false, 'form']], target: 'current', context: { default_state: 'draft' }
        });
    }
}

CustomsDashboard.template = "customs_clearance_ksa.Dashboard";
registry.category("actions").add("customs_clearance_ksa.dashboard", CustomsDashboard);
