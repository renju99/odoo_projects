/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

// Basic dashboard functionality
export class FacilitiesDashboard extends Component {
    static template = "facilities_management.Dashboard";

    setup() {
        console.log("Facilities Dashboard initialized");
    }
}

// Register the component
registry.category("actions").add("facilities_dashboard", FacilitiesDashboard);

// Basic utility functions
window.facilitiesUtils = {
    formatCurrency: function(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    },

    formatDate: function(date) {
        return new Date(date).toLocaleDateString();
    },

    getSLAStatusClass: function(status) {
        const statusClasses = {
            'on_time': 'o_sla_on_time',
            'warning': 'o_sla_warning',
            'critical': 'o_sla_critical',
            'breached': 'o_sla_breached'
        };
        return statusClasses[status] || 'o_sla_on_time';
    }
};

console.log("Facilities Management JavaScript loaded");