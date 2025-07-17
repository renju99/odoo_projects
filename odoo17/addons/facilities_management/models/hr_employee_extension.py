from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    hourly_cost = fields.Float(
        string='Hourly Cost',
        default=50.0,
        help="Cost per hour for this employee"
    )
    is_technician = fields.Boolean(
        string='Is Technician',
        default=False,
        help="Check if this employee is a maintenance technician"
    )
    current_workload = fields.Float(
        string='Current Workload (%)',
        compute='_compute_current_workload',
        help="Current workload percentage based on active work orders"
    )

    def _compute_current_workload(self):
        for employee in self:
            # Only compute if maintenance workorder model exists
            if 'maintenance.workorder' in self.env:
                try:
                    # Calculate current workload based on active work orders
                    active_workorders = self.env['maintenance.workorder'].search([
                        ('assigned_technician_ids', 'in', employee.id),
                        ('status', 'in', ['draft', 'in_progress'])
                    ])
                    # Simple calculation: each active workorder = 20% workload (max 100%)
                    employee.current_workload = min(100.0, len(active_workorders) * 20.0)
                except Exception:
                    employee.current_workload = 0.0
            else:
                employee.current_workload = 0.0