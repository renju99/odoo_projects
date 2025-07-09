# models/maintenance_workorder_assignment.py
from odoo import models, fields

class MaintenanceWorkOrderAssignment(models.Model):
    _name = 'maintenance.workorder.assignment'
    _description = 'Maintenance Work Order Technician Assignment'
    _rec_name = 'technician_id' # Display technician name in relation

    workorder_id = fields.Many2one(
        'maintenance.workorder',
        string='Work Order',
        required=True,
        ondelete='cascade' # If work order is deleted, assignments are deleted
    )
    technician_id = fields.Many2one(
        'hr.employee',
        string="Technician",
        required=True
    )
    start_date = fields.Datetime(string="Start Date", default=fields.Datetime.now)
    end_date = fields.Datetime(string="End Date")

    _sql_constraints = [
        ('unique_technician_per_workorder_date', 'UNIQUE(workorder_id, technician_id, start_date)', 'A technician can only be assigned once to the same work order at the exact same start time. Please adjust the start date/time or add a new assignment.'),
    ]