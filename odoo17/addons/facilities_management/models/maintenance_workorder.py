# models/maintenance_workorder.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
# from datetime import datetime # Ensure datetime is imported if not already, for fields.Datetime.now()

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
        domain="[('active','=',True)]",
        ondelete='set null'
    )
    work_order_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection'),
        ('repair', 'Repair'),
    ], string='Work Order Type', required=True, default='corrective', tracking=True)

    technician_id = fields.Many2one(
        'hr.employee',
        string="Technician",
        default=lambda self: self._default_technician(),
        tracking=True
    )

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
    start_date = fields.Datetime(string="Scheduled Start", default=fields.Datetime.now)
    end_date = fields.Datetime(string="Scheduled End")

    actual_start_date = fields.Datetime(string="Actual Start Date", readonly=True)
    actual_end_date = fields.Datetime(string="Actual End Date", readonly=True)

    status = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)

    def _default_technician(self):
        employee = self.env.user.employee_id
        return employee.id if employee else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.workorder') or 'New'
            if not vals.get('technician_id'):
                vals['technician_id'] = self._default_technician()
        return super().create(vals_list)

    # --- Status Transition Methods ---

    def action_start_progress(self):
        """Moves work order to 'In Progress' state and sets actual start date."""
        for rec in self:
            if rec.status == 'draft':
                rec.write({
                    'status': 'in_progress',
                    'actual_start_date': fields.Datetime.now(),
                })
            else:
                raise UserError(_("Work order must be in 'Draft' state to start progress."))

    def action_complete(self):
        """Moves work order to 'Completed' state and sets actual end date."""
        for rec in self:
            if rec.status == 'in_progress':
                rec.write({
                    'status': 'done',
                    'actual_end_date': fields.Datetime.now(),
                })
                # NEW LOGIC: Update the last_maintenance_date on the associated schedule
                if rec.schedule_id and rec.actual_end_date:
                    # Convert datetime to date, as last_maintenance_date is a Date field
                    rec.schedule_id.last_maintenance_date = rec.actual_end_date.date()
            else:
                raise UserError(_("Work order must be 'In Progress' to complete."))

    def action_cancel(self):
        """Cancels the work order."""
        for rec in self:
            if rec.status in ('draft', 'in_progress'):
                rec.write({'status': 'cancelled'})
            else:
                raise UserError(_("Work order can only be cancelled from 'Draft' or 'In Progress' states."))

    def action_reset_to_draft(self):
        """Resets a cancelled or completed work order back to draft. Use with caution."""
        for rec in self:
            if rec.status in ('done', 'cancelled'):
                rec.write({
                    'status': 'draft',
                    'actual_start_date': False,
                    'actual_end_date': False,
                })
            else:
                raise UserError(_("Work order can only be reset from 'Completed' or 'Cancelled' states."))