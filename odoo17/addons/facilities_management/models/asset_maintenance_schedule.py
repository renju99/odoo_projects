# models/asset_maintenance_schedule.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta, date # Ensure 'date' is imported

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
    notes = fields.Text(string='Notes')

    active = fields.Boolean(string='Active', default=False, tracking=True)

    # ADD THIS MISSING 'status' FIELD
    status = fields.Selection([
        ('draft', 'Draft'),
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True) # Added tracking=True for status changes

    @api.depends('last_maintenance_date', 'interval_number', 'interval_type')
    def _compute_next_maintenance_date(self):
        for rec in self:
            if rec.last_maintenance_date and rec.interval_number > 0:
                current_date = rec.last_maintenance_date
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
                    rec.next_maintenance_date = current_date + relativedelta(months=rec.interval_number * 3)
                elif rec.interval_type == 'yearly':
                    rec.next_maintenance_date = current_date + relativedelta(years=rec.interval_number)
                else:
                    rec.next_maintenance_date = False
            else:
                rec.next_maintenance_date = False

    def _generate_preventive_workorders(self):
        today = fields.Date.today()
        # Search for active schedules whose 'next_maintenance_date'
        # is between today and 7 days from now (inclusive).
        due_schedules = self.search([
            ('active', '=', True),
            ('next_maintenance_date', '>=', today), # Due today or in the future
            ('next_maintenance_date', '<=', today + timedelta(days=7)), # Due within the next 7 days
        ])

        for schedule in due_schedules:
            # Check if a work order for THIS specific 'next_maintenance_date'
            # already exists and is not yet 'done' or 'cancelled'.
            existing_workorder = self.env['maintenance.workorder'].search([
                ('schedule_id', '=', schedule.id),
                ('start_date', '=', schedule.next_maintenance_date), # Assuming start_date is the planned due date
                ('status', 'not in', ['done', 'cancelled']),
            ], limit=1)

            if not existing_workorder:
                self.env['maintenance.workorder'].create({
                    'name': _('Preventive Work Order for %s (%s)') % (schedule.asset_id.name, schedule.name),
                    'asset_id': schedule.asset_id.id,
                    'schedule_id': schedule.id,
                    'work_order_type': 'preventive',
                    'start_date': schedule.next_maintenance_date, # Work order is planned for the actual due date
                    'status': 'draft', # Work order starts in draft
                })
                # IMPORTANT: We DO NOT update schedule.last_maintenance_date here.
                # It should be updated when the associated work order is completed.
                # This will be handled in the maintenance.workorder model's 'action_complete' method.