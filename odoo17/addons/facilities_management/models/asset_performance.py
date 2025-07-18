from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date
import logging

_logger = logging.getLogger(__name__)


class AssetPerformance(models.Model):
    _name = 'facilities.asset.performance'
    _description = 'Asset Performance Tracking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, asset_id'
    _rec_name = 'display_name'

    # Basic Information
    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True,
                               ondelete='cascade', index=True, tracking=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today,
                       tracking=True, index=True)

    # Performance Metrics (in hours)
    expected_daily_runtime = fields.Float(string='Expected Daily Runtime (Hours)',
                                          default=8.0, required=True, tracking=True,
                                          help="Expected operating hours per day for this asset")
    actual_runtime = fields.Float(string='Actual Runtime (Hours)',
                                  required=True, tracking=True,
                                  help="Actual operating hours recorded for this day")
    downtime_hours = fields.Float(string='Downtime (Hours)',
                                  tracking=True, default=0.0,
                                  help="Hours the asset was down/not operational")

    # Computed Performance Indicators
    runtime_percentage = fields.Float(string='Runtime Efficiency (%)',
                                      compute='_compute_performance_metrics',
                                      store=True, group_operator='avg')
    availability_percentage = fields.Float(string='Availability (%)',
                                           compute='_compute_performance_metrics',
                                           store=True, group_operator='avg')
    utilization_percentage = fields.Float(string='Utilization (%)',
                                          compute='_compute_performance_metrics',
                                          store=True, group_operator='avg')

    # Additional Information
    notes = fields.Text(string='Performance Notes')
    operator_id = fields.Many2one('res.users', string='Operator/Responsible',
                                  default=lambda self: self.env.user, tracking=True)
    shift = fields.Selection([
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('night', 'Night'),
        ('full_day', 'Full Day')
    ], string='Shift', default='full_day', tracking=True)

    # Performance Status
    performance_status = fields.Selection([
        ('excellent', 'Excellent (≥95%)'),
        ('good', 'Good (80-94%)'),
        ('average', 'Average (60-79%)'),
        ('poor', 'Poor (<60%)')
    ], string='Performance Status', compute='_compute_performance_status',
        store=True, tracking=True)

    # Downtime Reasons
    downtime_reason_ids = fields.Many2many('asset.downtime.reason',
                                           string='Downtime Reasons')

    # Technical fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company,
                                 help="Company this performance record belongs to")

    _sql_constraints = [
        ('unique_asset_date_shift', 'unique(asset_id, date, shift)',
         'Performance record already exists for this asset, date, and shift!'),
        ('positive_expected_runtime', 'CHECK(expected_daily_runtime > 0)',
         'Expected daily runtime must be positive!'),
        ('positive_actual_runtime', 'CHECK(actual_runtime >= 0)',
         'Actual runtime cannot be negative!'),
        ('positive_downtime', 'CHECK(downtime_hours >= 0)',
         'Downtime cannot be negative!'),
    ]

    @api.depends('asset_id', 'date', 'shift')
    def _compute_display_name(self):
        for record in self:
            if record.asset_id and record.date:
                record.display_name = f"{record.asset_id.name} - {record.date} ({record.shift or 'N/A'})"
            else:
                record.display_name = "New Performance Record"

    @api.depends('expected_daily_runtime', 'actual_runtime', 'downtime_hours')
    def _compute_performance_metrics(self):
        for record in self:
            if record.expected_daily_runtime > 0:
                # Runtime Efficiency: Actual vs Expected
                record.runtime_percentage = (record.actual_runtime / record.expected_daily_runtime) * 100

                # Availability: (Expected - Downtime) / Expected
                available_time = max(0, record.expected_daily_runtime - record.downtime_hours)
                record.availability_percentage = (available_time / record.expected_daily_runtime) * 100

                # Utilization: Actual / Available Time
                if available_time > 0:
                    record.utilization_percentage = min(100, (record.actual_runtime / available_time) * 100)
                else:
                    record.utilization_percentage = 0.0
            else:
                record.runtime_percentage = 0.0
                record.availability_percentage = 0.0
                record.utilization_percentage = 0.0

    @api.depends('availability_percentage')
    def _compute_performance_status(self):
        for record in self:
            if record.availability_percentage >= 95:
                record.performance_status = 'excellent'
            elif record.availability_percentage >= 80:
                record.performance_status = 'good'
            elif record.availability_percentage >= 60:
                record.performance_status = 'average'
            else:
                record.performance_status = 'poor'

    @api.constrains('actual_runtime', 'downtime_hours', 'expected_daily_runtime')
    def _check_time_logic(self):
        for record in self:
            # Check if actual runtime + downtime doesn't exceed 24 hours unreasonably
            total_time = record.actual_runtime + record.downtime_hours
            if total_time > 24:
                raise ValidationError(_("Total runtime and downtime cannot exceed 24 hours per day."))

            # Warn if actual runtime exceeds expected significantly
            if record.actual_runtime > record.expected_daily_runtime * 1.5:
                _logger.warning(f"Asset {record.asset_id.name} actual runtime ({record.actual_runtime}h) "
                                f"significantly exceeds expected ({record.expected_daily_runtime}h) on {record.date}")

    def action_view_performance_analysis(self):
        """Open performance analysis for this asset"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Performance Analysis - {self.asset_id.name}',
            'res_model': 'facilities.asset.performance',
            'view_mode': 'graph,pivot,tree',
            'domain': [('asset_id', '=', self.asset_id.id)],
            'context': {
                'search_default_group_by_date': 1,
                'search_default_last_30_days': 1,
            }
        }


class AssetDowntimeReason(models.Model):
    _name = 'asset.downtime.reason'
    _description = 'Asset Downtime Reason'
    _order = 'sequence, name'

    name = fields.Char(string='Reason', required=True, translate=True)
    code = fields.Char(string='Code', size=10)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    category = fields.Selection([
        ('mechanical', 'Mechanical Failure'),
        ('electrical', 'Electrical Issue'),
        ('maintenance', 'Scheduled Maintenance'),
        ('material', 'Material/Supply Issue'),
        ('operator', 'Operator Issue'),
        ('environmental', 'Environmental'),
        ('other', 'Other')
    ], string='Category', required=True, default='other')
    active = fields.Boolean(string='Active', default=True)
    color = fields.Integer(string='Color', default=0)

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Downtime reason code must be unique!')
    ]