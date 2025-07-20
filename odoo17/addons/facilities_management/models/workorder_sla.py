from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class MaintenanceWorkOrderSLA(models.Model):
    _name = 'maintenance.workorder.sla'
    _description = 'Work Order SLA Configuration'
    _rec_name = 'name'
    _order = 'sequence, id'

    name = fields.Char(string='SLA Name', required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(string='Sequence', default=10, help="Lower sequence = higher priority for matching")

    # SLA Criteria
    priority = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High'),
    ], string='Priority', help="Leave empty to apply to all priorities")

    facility_id = fields.Many2one('facilities.facility', string='Facility', help="Leave empty to apply to all facilities")
    location = fields.Char(string='Location', help="Leave empty to apply to all locations")
    work_order_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection'),
    ], string='Work Order Type', help="Leave empty to apply to all types")

    response_time_hours = fields.Float(string='Response Time (Hours)', required=True, default=4.0, help="Time to acknowledge/start work")
    resolution_time_hours = fields.Float(string='Resolution Time (Hours)', required=True, default=24.0, help="Time to complete work")

    warning_threshold = fields.Float(string='Warning Threshold (%)', default=80.0, help="Send warning when SLA reaches this percentage")
    critical_threshold = fields.Float(string='Critical Threshold (%)', default=95.0, help="Send critical alert when SLA reaches this percentage")

    escalation_enabled = fields.Boolean(string='Enable Escalation', default=True)
    escalation_manager_id = fields.Many2one('hr.employee', string='Escalation Manager', domain="[('user_id', '!=', False)]")

    @api.model
    def find_matching_sla(self, workorder):
        """
        Find the most specific, active SLA configuration for a work order.
        Uses a weighted score: priority (4), facility (3), location (2), type (1).
        """
        domain = [('active', '=', True)]
        all_slas = self.search(domain, order='sequence asc')

        # Attempt to get facility and location via asset, fallback to direct field
        facility_id = getattr(workorder.asset_id, 'facility_id', None)
        if facility_id:
            facility_id = facility_id.id
        else:
            facility_id = getattr(workorder, 'facility_id', False)
            facility_id = facility_id.id if facility_id else False

        location = getattr(workorder.asset_id, 'location', None) or getattr(workorder, 'location', None)

        best_sla = None
        best_score = -1

        for sla in all_slas:
            score = 0
            matches = True

            # Priority
            if sla.priority and sla.priority != workorder.priority:
                matches = False
            elif sla.priority and sla.priority == workorder.priority:
                score += 4

            # Facility
            if sla.facility_id and facility_id and sla.facility_id.id != facility_id:
                matches = False
            elif sla.facility_id and facility_id and sla.facility_id.id == facility_id:
                score += 3

            # Location
            sla_loc = sla.location.lower().strip() if sla.location else ""
            wo_loc = (location or "").lower().strip()
            if sla.location and wo_loc and sla_loc != wo_loc:
                matches = False
            elif sla.location and wo_loc and sla_loc == wo_loc:
                score += 2

            # WO Type
            if sla.work_order_type and sla.work_order_type != workorder.work_order_type:
                matches = False
            elif sla.work_order_type and sla.work_order_type == workorder.work_order_type:
                score += 1

            if matches and score > best_score:
                best_score = score
                best_sla = sla

        return best_sla

    @api.constrains('warning_threshold', 'critical_threshold')
    def _check_thresholds(self):
        for record in self:
            if record.warning_threshold >= record.critical_threshold:
                raise ValidationError(_("Warning threshold must be less than critical threshold"))
            if record.warning_threshold <= 0 or record.critical_threshold <= 0:
                raise ValidationError(_("Thresholds must be positive values"))
            if record.warning_threshold > 100 or record.critical_threshold > 100:
                raise ValidationError(_("Thresholds cannot exceed 100%"))

    @api.constrains('response_time_hours', 'resolution_time_hours')
    def _check_time_hours(self):
        for record in self:
            if record.response_time_hours <= 0 or record.resolution_time_hours <= 0:
                raise ValidationError(_("Time hours must be positive values"))
            if record.response_time_hours >= record.resolution_time_hours:
                raise ValidationError(_("Response time must be less than resolution time"))