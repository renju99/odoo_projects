from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError


class MaintenanceWorkOrder(models.Model):
    _inherit = 'maintenance.workorder'

    # SLA Fields
    sla_id = fields.Many2one('maintenance.workorder.sla', string='Applied SLA', readonly=True)
    sla_response_deadline = fields.Datetime(string='Response Deadline', readonly=True)
    sla_resolution_deadline = fields.Datetime(string='Resolution Deadline', readonly=True)
    sla_response_status = fields.Selection([
        ('on_time', 'On Time'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('breached', 'Breached')
    ], string='Response SLA Status', compute='_compute_sla_status', store=True)
    sla_resolution_status = fields.Selection([
        ('on_time', 'On Time'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('breached', 'Breached')
    ], string='Resolution SLA Status', compute='_compute_sla_status', store=True)

    # Resource Utilization
    resource_utilization_ids = fields.One2many('maintenance.resource.utilization', 'workorder_id',
                                               string='Resource Utilization')
    total_resource_hours = fields.Float(string='Total Resource Hours',
                                        compute='_compute_resource_metrics', store=True)
    total_resource_cost = fields.Float(string='Total Resource Cost',
                                       compute='_compute_resource_metrics', store=True)
    resource_efficiency = fields.Float(string='Resource Efficiency (%)',
                                       compute='_compute_resource_metrics', store=True)

    # Enhanced assignment tracking
    assigned_technician_ids = fields.Many2many('hr.employee', 'workorder_technician_rel',
                                               'workorder_id', 'employee_id',
                                               string='Assigned Technicians',
                                               domain="[('is_technician', '=', True)]")

    @api.model
    def create(self, vals):
        workorder = super().create(vals)
        workorder._apply_sla()
        return workorder

    def write(self, vals):
        result = super().write(vals)
        # Reapply SLA if relevant fields change
        if any(field in vals for field in ['priority', 'asset_id', 'work_order_type']):
            for record in self:
                record._apply_sla()
        return result

    def _apply_sla(self):
        """Apply appropriate SLA to the work order"""
        try:
            sla = self.env['maintenance.workorder.sla'].find_matching_sla(self)
            if sla:
                current_time = fields.Datetime.now()
                self.write({
                    'sla_id': sla.id,
                    'sla_response_deadline': current_time + timedelta(hours=sla.response_time_hours),
                    'sla_resolution_deadline': current_time + timedelta(hours=sla.resolution_time_hours),
                })
        except Exception:
            # If SLA model doesn't exist yet, skip
            pass

    @api.depends('sla_response_deadline', 'sla_resolution_deadline', 'actual_start_date', 'actual_end_date', 'status')
    def _compute_sla_status(self):
        for record in self:
            if not record.sla_response_deadline:
                record.sla_response_status = 'on_time'
                record.sla_resolution_status = 'on_time'
                continue

            current_time = fields.Datetime.now()

            # Response SLA Status
            if record.actual_start_date:
                record.sla_response_status = 'on_time'
            else:
                time_remaining = (record.sla_response_deadline - current_time).total_seconds()
                total_time = (record.sla_response_deadline - record.create_date).total_seconds()
                percentage_used = ((total_time - time_remaining) / total_time) * 100 if total_time > 0 else 0

                if time_remaining <= 0:
                    record.sla_response_status = 'breached'
                elif percentage_used >= (record.sla_id.critical_threshold if record.sla_id else 95):
                    record.sla_response_status = 'critical'
                elif percentage_used >= (record.sla_id.warning_threshold if record.sla_id else 80):
                    record.sla_response_status = 'warning'
                else:
                    record.sla_response_status = 'on_time'

            # Resolution SLA Status
            if record.status == 'done':
                record.sla_resolution_status = 'on_time'
            else:
                time_remaining = (record.sla_resolution_deadline - current_time).total_seconds()
                total_time = (record.sla_resolution_deadline - record.create_date).total_seconds()
                percentage_used = ((total_time - time_remaining) / total_time) * 100 if total_time > 0 else 0

                if time_remaining <= 0:
                    record.sla_resolution_status = 'breached'
                elif percentage_used >= (record.sla_id.critical_threshold if record.sla_id else 95):
                    record.sla_resolution_status = 'critical'
                elif percentage_used >= (record.sla_id.warning_threshold if record.sla_id else 80):
                    record.sla_resolution_status = 'warning'
                else:
                    record.sla_resolution_status = 'on_time'

    @api.depends('resource_utilization_ids.hours_logged', 'resource_utilization_ids.total_cost')
    def _compute_resource_metrics(self):
        for record in self:
            record.total_resource_hours = sum(record.resource_utilization_ids.mapped('hours_logged'))
            record.total_resource_cost = sum(record.resource_utilization_ids.mapped('total_cost'))

            # Calculate efficiency based on estimated vs actual hours
            estimated_duration = 0
            if record.end_date and record.start_date:
                estimated_duration = (record.end_date - record.start_date).total_seconds() / 3600.0

            if estimated_duration > 0 and record.total_resource_hours > 0:
                record.resource_efficiency = (estimated_duration / record.total_resource_hours) * 100
            else:
                record.resource_efficiency = 100.0

    def action_start_progress(self):
        """Override to track SLA response time and start resource utilization"""
        result = super().action_start_progress()

        # Create initial resource utilization records for assigned technicians
        for technician in self.assigned_technician_ids:
            self.env['maintenance.resource.utilization'].create({
                'workorder_id': self.id,
                'employee_id': technician.id,
                'start_time': fields.Datetime.now(),
                'utilization_type': 'work',
                'notes': f'Started work on {self.name}',
            })
        return result

    def action_complete(self):
        """Override to finalize resource utilization"""
        # Close any open resource utilization records
        open_utilizations = self.resource_utilization_ids.filtered(lambda r: not r.end_time)
        for util in open_utilizations:
            util.end_time = fields.Datetime.now()

        return super().action_complete()

    def action_start_time_tracking(self):
        """Start time tracking for assigned technicians"""
        self.ensure_one()
        if not self.assigned_technician_ids:
            raise UserError(_("Please assign technicians before starting time tracking."))

        # Create time tracking entries for assigned technicians
        for technician in self.assigned_technician_ids:
            existing_active = self.env['maintenance.resource.utilization'].search([
                ('employee_id', '=', technician.id),
                ('workorder_id', '=', self.id),
                ('is_active', '=', True)
            ])
            if not existing_active:
                self.env['maintenance.resource.utilization'].create({
                    'workorder_id': self.id,
                    'employee_id': technician.id,
                    'start_time': fields.Datetime.now(),
                    'utilization_type': 'work',
                    'notes': f'Manual time tracking started for {self.name}',
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Time Tracking Started'),
                'message': f'Time tracking started for {len(self.assigned_technician_ids)} technician(s)',
                'type': 'success',
            }
        }

    def action_stop_time_tracking(self):
        """Stop time tracking for all active entries"""
        self.ensure_one()
        active_entries = self.resource_utilization_ids.filtered(lambda r: r.is_active)
        stopped_count = 0
        for entry in active_entries:
            entry.action_stop_time_tracking()
            stopped_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Time Tracking Stopped'),
                'message': f'Stopped time tracking for {stopped_count} active entries',
                'type': 'success',
            }
        }

    def get_sla_progress(self):
        """Get SLA progress as percentage"""
        self.ensure_one()
        if not self.sla_response_deadline:
            return {'response': 0, 'resolution': 0}

        current_time = fields.Datetime.now()

        # Response progress
        total_response_time = (self.sla_response_deadline - self.create_date).total_seconds()
        elapsed_response_time = (current_time - self.create_date).total_seconds()
        response_progress = min(100,
                                (elapsed_response_time / total_response_time) * 100) if total_response_time > 0 else 0

        # Resolution progress
        total_resolution_time = (self.sla_resolution_deadline - self.create_date).total_seconds()
        elapsed_resolution_time = (current_time - self.create_date).total_seconds()
        resolution_progress = min(100, (
                    elapsed_resolution_time / total_resolution_time) * 100) if total_resolution_time > 0 else 0

        return {
            'response': response_progress,
            'resolution': resolution_progress
        }