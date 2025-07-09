# models/asset_maintenance_schedule.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
# If you plan to use relativedelta for precise date calculations, uncomment this:
# from dateutil.relativedelta import relativedelta


class AssetMaintenanceSchedule(models.Model):
    _name = 'asset.maintenance.schedule'
    _description = 'Asset Maintenance Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Schedule Name', required=True, tracking=True)
    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True, tracking=True)
    maintenance_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection'),
    ], string='Maintenance Type', required=True, default='preventive', tracking=True)

    interval_number = fields.Integer(string='Repeat Every', default=1, required=True, tracking=True)
    interval_type = fields.Selection([
        ('daily', 'Day(s)'),
        ('weekly', 'Week(s)'),
        ('monthly', 'Month(s)'),
        ('quarterly', 'Quarter(s)'),
        ('yearly', 'Year(s)'),
    ], string='Recurrence', default='monthly', required=True, tracking=True)

    last_maintenance_date = fields.Date(string='Last Maintenance Date', tracking=True)
    next_maintenance_date = fields.Date(string='Next Scheduled Date', compute='_compute_next_maintenance_date', store=True, tracking=True)
    status = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='planned', tracking=True)
    notes = fields.Text(string='Notes')

    # New: Active/Deactivated field
    active = fields.Boolean(string='Active', default=True, tracking=True)

    @api.depends('last_maintenance_date', 'interval_number', 'interval_type')
    def _compute_next_maintenance_date(self):
        for rec in self:
            if rec.last_maintenance_date and rec.interval_number > 0:
                current_date = rec.last_maintenance_date
                # Using relativedelta for accurate date calculations (requires 'python-dateutil')
                try:
                    from dateutil.relativedelta import relativedelta
                except ImportError:
                    raise UserError(_("The 'python-dateutil' library is not installed. Please install it ('pip install python-dateutil') for accurate date calculations."))

                if rec.interval_type == 'daily':
                    rec.next_maintenance_date = current_date + relativedelta(days=rec.interval_number)
                elif rec.interval_type == 'weekly':
                    rec.next_maintenance_date = current_date + relativedelta(weeks=rec.interval_number)
                elif rec.interval_type == 'monthly':
                    rec.next_maintenance_date = current_date + relativedelta(months=rec.interval_number)
                elif rec.interval_type == 'quarterly':
                    rec.next_maintenance_date = current_date + relativedelta(months=rec.interval_number * 3) # 1 quarter = 3 months
                elif rec.interval_type == 'yearly':
                    rec.next_maintenance_date = current_date + relativedelta(years=rec.interval_number)
                else:
                    rec.next_maintenance_date = False
            else:
                rec.next_maintenance_date = False

    # Example: Method to generate work orders (can be called by a cron job)
    def action_generate_workorders(self):
        # Only generate work orders for active and planned schedules
        for schedule in self.filtered(lambda s: s.active and s.next_maintenance_date and s.next_maintenance_date <= fields.Date.today() and s.status == 'planned'):
            self.env['maintenance.workorder'].create({
                'name': _('Work Order for %s (%s)') % (schedule.asset_id.name, schedule.name),
                'asset_id': schedule.asset_id.id,
                'work_order_type': schedule.maintenance_type,
                'schedule_id': schedule.id,
                'start_date': schedule.next_maintenance_date,
                # Add other fields as necessary
            })
            # Update last maintenance date and recalculate next_maintenance_date
            schedule.last_maintenance_date = fields.Date.today()
            schedule.status = 'in_progress' # Or 'done' depending on your workflow