from odoo import models, fields, api, tools
from datetime import datetime, timedelta

class WorkOrderSLAAnalytics(models.Model):
    _name = 'maintenance.sla.analytics'
    _description = 'SLA Analytics and Reports'
    _auto = False

    workorder_id = fields.Many2one('maintenance.workorder', string='Work Order')
    sla_id = fields.Many2one('maintenance.workorder.sla', string='SLA')
    priority = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High'),
    ], string='Priority')
    facility_id = fields.Many2one('facilities.facility', string='Facility')
    response_sla_met = fields.Boolean(string='Response SLA Met')
    resolution_sla_met = fields.Boolean(string='Resolution SLA Met')
    response_time_hours = fields.Float(string='Actual Response Time (Hours)')
    resolution_time_hours = fields.Float(string='Actual Resolution Time (Hours)')
    sla_response_target = fields.Float(string='Response SLA Target')
    sla_resolution_target = fields.Float(string='Resolution SLA Target')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    wo.id,
                    wo.id as workorder_id,
                    wo.sla_id,
                    wo.priority,
                    a.facility_id,
                    CASE 
                        WHEN wo.actual_start_date IS NOT NULL AND wo.sla_response_deadline IS NOT NULL
                        THEN wo.actual_start_date <= wo.sla_response_deadline
                        ELSE TRUE
                    END as response_sla_met,
                    CASE 
                        WHEN wo.actual_end_date IS NOT NULL AND wo.sla_resolution_deadline IS NOT NULL
                        THEN wo.actual_end_date <= wo.sla_resolution_deadline
                        ELSE TRUE
                    END as resolution_sla_met,
                    CASE 
                        WHEN wo.actual_start_date IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (wo.actual_start_date - wo.create_date)) / 3600.0
                        ELSE NULL
                    END as response_time_hours,
                    CASE 
                        WHEN wo.actual_end_date IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (wo.actual_end_date - wo.create_date)) / 3600.0
                        ELSE NULL
                    END as resolution_time_hours,
                    sla.response_time_hours as sla_response_target,
                    sla.resolution_time_hours as sla_resolution_target
                FROM maintenance_workorder wo
                LEFT JOIN facilities_asset a ON wo.asset_id = a.id
                LEFT JOIN maintenance_workorder_sla sla ON wo.sla_id = sla.id
            )
        """ % self._table)