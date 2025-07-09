# models/maintenance_workorder.py
from odoo import models, fields, api

class MaintenanceWorkOrder(models.Model):
    _name = 'maintenance.workorder'
    _description = 'Maintenance Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference',
        required=True,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('maintenance.workorder') or 'New'
    )
    schedule_id = fields.Many2one(
        'asset.maintenance.schedule',
        string="Schedule",
        domain="[('status','=','planned')]",
        ondelete='set null'
    )
    work_order_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection'),
        ('repair', 'Repair'),
    ], string='Work Order Type', required=True, default='corrective', tracking=True)

    # RE-ADD THE technician_id FIELD HERE
    technician_id = fields.Many2one(
        'hr.employee',
        string="Technician",
        default=lambda self: self._default_technician(),
        tracking=True
    )

    # The One2Many field for technician assignments (keep this if you want both)
    assignment_ids = fields.One2many(
        'maintenance.workorder.assignment',
        'workorder_id',
        string='Technician Assignments'
    )

    asset_id = fields.Many2one(
        'facilities.asset',
        string="Asset",
        required=True,
        tracking=True
    )
    start_date = fields.Datetime(default=fields.Datetime.now)
    end_date = fields.Datetime()
    status = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)

    # RE-ADD THE _default_technician METHOD
    def _default_technician(self):
        employee = self.env.user.employee_id
        return employee.id if employee else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.workorder') or 'New'
            # Ensure technician_id is set if not provided and using default
            if not vals.get('technician_id'):
                vals['technician_id'] = self._default_technician()
        return super().create(vals_list)