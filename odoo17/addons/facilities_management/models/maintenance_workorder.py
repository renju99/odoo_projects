# models/maintenance_workorder.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
# from datetime import datetime # Ensure datetime is imported if not already, for fields.Datetime.now()


class MaintenanceWorkOrder(models.Model):
    _name = 'maintenance.workorder'
    _description = 'Maintenance Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Existing fields
    name = fields.Char(string='Work Order Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True)
    schedule_id = fields.Many2one('asset.maintenance.schedule', string='Maintenance Schedule')
    work_order_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection'),
    ], string='Type', default='corrective', required=True)
    technician_id = fields.Many2one('hr.employee', string='Primary Technician', domain="[('is_technician', '=', True)]")
    start_date = fields.Datetime(string='Scheduled Start Date')
    end_date = fields.Datetime(string='Scheduled End Date')
    actual_start_date = fields.Datetime(string='Actual Start Date', readonly=True)
    actual_end_date = fields.Datetime(string='Actual End Date', readonly=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status', tracking=True)
    assignment_ids = fields.One2many('maintenance.workorder.assignment', 'workorder_id', string='Assignments')
    priority = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High'),
    ], string='Priority', default='1')

    # NEW FIELDS ADDED HERE:
    description = fields.Text(string='Work Order Description')
    work_done = fields.Text(string='Work Done Notes')
    parts_used_ids = fields.One2many('maintenance.workorder.part_line', 'workorder_id', string='Parts Used')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.workorder') or _('New')
        return super().create(vals_list)

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
        """Moves work order to 'Cancelled' state."""
        for rec in self:
            if rec.status not in ('done', 'cancelled'):
                rec.write({'status': 'cancelled'})
            else:
                raise UserError(_("Cannot cancel a completed or already cancelled work order."))

    def action_reset_to_draft(self):
        """Resets a completed or cancelled work order back to 'Draft'."""
        for rec in self:
            if rec.status in ('done', 'cancelled'):
                rec.write({
                    'status': 'draft',
                    'actual_start_date': False,
                    'actual_end_date': False,
                })
            else:
                raise UserError(_("Only completed or cancelled work orders can be reset to draft."))

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        if self.asset_id:
            # Set default technician from asset's responsible person if not already set
            if self.asset_id.responsible_id and not self.technician_id:
                # Find the hr.employee record linked to the res.users responsible_id
                employee = self.env['hr.employee'].search([('user_id', '=', self.asset_id.responsible_id.id)], limit=1)
                if employee:
                    self.technician_id = employee.id

    # ... (You might have other methods here)