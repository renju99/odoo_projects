from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MaintenanceResourceUtilization(models.Model):
    _name = 'maintenance.resource.utilization'
    _description = 'Resource Utilization Tracking'
    _order = 'start_time desc'

    workorder_id = fields.Many2one('maintenance.workorder', string='Work Order',
                                   required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    start_time = fields.Datetime(string='Start Time', required=True, default=fields.Datetime.now)
    end_time = fields.Datetime(string='End Time')
    hours_logged = fields.Float(string='Hours Logged', compute='_compute_hours_logged', store=True)

    utilization_type = fields.Selection([
        ('work', 'Active Work'),
        ('travel', 'Travel Time'),
        ('wait', 'Waiting'),
        ('break', 'Break'),
    ], string='Utilization Type', default='work', required=True)

    notes = fields.Text(string='Notes')
    hourly_rate = fields.Float(string='Hourly Rate', related='employee_id.hourly_cost', readonly=True)
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)

    # Status tracking
    is_active = fields.Boolean(string='Is Active', compute='_compute_is_active', store=True)

    @api.depends('start_time', 'end_time')
    def _compute_hours_logged(self):
        for record in self:
            if record.start_time and record.end_time:
                delta = record.end_time - record.start_time
                record.hours_logged = delta.total_seconds() / 3600.0
            else:
                record.hours_logged = 0.0

    @api.depends('hours_logged', 'hourly_rate')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.hours_logged * (record.hourly_rate or 0.0)

    @api.depends('end_time')
    def _compute_is_active(self):
        for record in self:
            record.is_active = not bool(record.end_time)

    @api.constrains('start_time', 'end_time')
    def _check_time_validity(self):
        for record in self:
            if record.end_time and record.start_time and record.end_time < record.start_time:
                raise ValidationError(_("End time cannot be before start time"))

    def action_stop_time_tracking(self):
        """Stop time tracking for this resource utilization entry"""
        self.ensure_one()
        if not self.end_time:
            self.end_time = fields.Datetime.now()
        return True

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.employee_id.name} - {record.workorder_id.name} ({record.utilization_type})"
            result.append((record.id, name))
        return result