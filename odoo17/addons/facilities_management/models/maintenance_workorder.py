from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

APPROVAL_STATES = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('supervisor', 'Supervisor Approved'),
    ('manager', 'Manager Approved'),
    ('approved', 'Fully Approved'),
    ('in_progress', 'In Progress'),
    ('done', 'Completed'),
    ('refused', 'Refused'),
    ('cancelled', 'Cancelled'),
    ('escalated', 'Escalated'),
]

class MaintenanceWorkOrder(models.Model):
    _name = 'maintenance.workorder'
    _description = 'Maintenance Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Work Order Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True)
    facility_id = fields.Many2one('facilities.facility', string='Facility',
                                  related='asset_id.facility_id', store=True, readonly=True)
    room_id = fields.Many2one('facilities.room', string='Room',
                              related='asset_id.room_id', store=True, readonly=True)
    building_id = fields.Many2one('facilities.building', string='Building',
                                  related='asset_id.building_id', store=True, readonly=True)
    floor_id = fields.Many2one('facilities.floor', string='Floor',
                               related='asset_id.floor_id', store=True, readonly=True)
    schedule_id = fields.Many2one('asset.maintenance.schedule', string='Maintenance Schedule')
    work_order_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive'),
        ('inspection', 'Inspection'),
    ], string='Type', default='corrective', required=True)
    technician_id = fields.Many2one('hr.employee', string='Primary Technician', domain="[('is_technician', '=', True)]")
    supervisor_id = fields.Many2one('res.users', string="Supervisor", readonly=True)
    permit_ids = fields.One2many('maintenance.workorder.permit', 'workorder_id', string='Permits')
    manager_id = fields.Many2one('res.users', string="Manager", readonly=True)
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
    description = fields.Text(string='Work Order Description')
    work_done = fields.Text(string='Work Done Notes')
    parts_used_ids = fields.One2many('maintenance.workorder.part_line', 'workorder_id', string='Parts Used')
    picking_id = fields.Many2one('stock.picking', string='Parts Transfer', copy=False,
                                 help="The internal transfer for parts issued for this work order.")
    picking_count = fields.Integer(compute='_compute_picking_count', string='Transfers')
    has_parts = fields.Boolean(compute='_compute_has_parts', store=True,
                               help="Indicates if this work order has parts lines.")

    service_type = fields.Selection([
        ('maintenance', 'Maintenance'),
        ('cleaning', 'Cleaning'),
        ('security', 'Security'),
        ('esg', 'ESG Compliance'),
        ('hse', 'HSE Incident')
    ], string="Service Type", tracking=True)
    maintenance_team_id = fields.Many2one('maintenance.team', string="Maintenance Team")
    section_ids = fields.One2many('maintenance.workorder.section', 'workorder_id', string='Sections')
    workorder_task_ids = fields.One2many('maintenance.workorder.task', 'workorder_id', string='Tasks', copy=True)
    all_tasks_completed = fields.Boolean(compute='_compute_all_tasks_completed', store=False)
    job_plan_id = fields.Many2one('maintenance.job.plan', string='Job Plan')

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

    approval_state = fields.Selection(
        APPROVAL_STATES, string="Approval State", default='draft', tracking=True
    )
    submitted_by_id = fields.Many2one('res.users', string="Submitted By", readonly=True)
    approved_by_id = fields.Many2one('res.users', string="Approved By", readonly=True)
    approval_request_date = fields.Datetime(string="Approval Requested At")
    escalation_deadline = fields.Datetime(string="Escalation Deadline")
    escalation_to_id = fields.Many2one('res.users', string="Escalate To")
    escalation_count = fields.Integer(string="Escalation Count", default=0, readonly=True)

    @api.onchange('technician_id')
    def _onchange_technician_fill_supervisor_manager(self):
        for rec in self:
            rec.supervisor_id, rec.manager_id = rec._get_supervisor_manager_from_technician(rec.technician_id)

    def _get_supervisor_manager_from_technician(self, technician):
        supervisor_user = False
        manager_user = False
        if technician and technician.parent_id and technician.parent_id.user_id:
            supervisor_user = technician.parent_id.user_id
            if technician.parent_id.parent_id and technician.parent_id.parent_id.user_id:
                manager_user = technician.parent_id.parent_id.user_id
        return supervisor_user, manager_user

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.workorder') or _('New')
            technician = self.env['hr.employee'].browse(vals.get('technician_id'))
            supervisor_user, manager_user = self._get_supervisor_manager_from_technician(technician)
            vals['supervisor_id'] = supervisor_user.id if supervisor_user else False
            vals['manager_id'] = manager_user.id if manager_user else False
        records = super().create(vals_list)
        for rec in records:
            if rec.job_plan_id:
                rec._copy_job_plan_sections_and_tasks()
            rec._apply_sla()
        return records

    def write(self, vals):
        if 'technician_id' in vals:
            technician = self.env['hr.employee'].browse(vals['technician_id'])
            supervisor_user, manager_user = self._get_supervisor_manager_from_technician(technician)
            vals['supervisor_id'] = supervisor_user.id if supervisor_user else False
            vals['manager_id'] = manager_user.id if manager_user else False
        result = super().write(vals)
        if any(field in vals for field in ['priority', 'asset_id', 'work_order_type']):
            for rec in self:
                rec._apply_sla()
        return result

    @api.depends('section_ids.task_ids.is_done', 'workorder_task_ids.is_done')
    def _compute_all_tasks_completed(self):
        for wo in self:
            sectioned_tasks = wo.section_ids.mapped('task_ids')
            flat_tasks = wo.workorder_task_ids
            all_tasks = sectioned_tasks | flat_tasks
            if not all_tasks:
                wo.all_tasks_completed = True
            else:
                wo.all_tasks_completed = all(task.is_done for task in all_tasks if task.is_checklist_item)

    @api.depends('parts_used_ids')
    def _compute_has_parts(self):
        for rec in self:
            rec.has_parts = bool(rec.parts_used_ids)

    @api.depends('picking_id')
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = 1 if rec.picking_id else 0

    def _apply_sla(self):
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

    def _sync_status_with_approval(self):
        for rec in self:
            if rec.approval_state in ['refused', 'cancelled', 'escalated']:
                rec.status = 'cancelled'
            elif rec.approval_state == 'done':
                rec.status = 'done'
            elif rec.approval_state == 'in_progress':
                rec.status = 'in_progress'
            elif rec.approval_state == 'draft':
                rec.status = 'draft'

    def _create_approval_activity(self, user, summary, note):
        if not user or not user.id:
            _logger.warning("No valid user for activity: %s", user)
            return
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        model_id = self.env['ir.model']._get_id('maintenance.workorder')
        self.env['mail.activity'].create({
            'activity_type_id': activity_type.id,
            'res_id': self.id,
            'res_model_id': model_id,
            'user_id': user.id,
            'summary': summary,
            'note': note,
            'date_deadline': fields.Date.today() + timedelta(days=1),
        })

    def action_submit_for_approval(self):
        for rec in self:
            if rec.approval_state != 'draft':
                raise UserError(_("Only draft work orders can be submitted!"))
            rec.write({
                'approval_state': 'submitted',
                'submitted_by_id': self.env.user.id,
                'approval_request_date': fields.Datetime.now(),
                'escalation_deadline': fields.Datetime.now() + timedelta(hours=24),
                'escalation_count': 0,
            })
            rec._sync_status_with_approval()
            if rec.supervisor_id:
                rec._create_approval_activity(
                    rec.supervisor_id,
                    _('Supervisor Approval Required'),
                    _('Please approve work order %s.') % rec.name
                )

    def action_supervisor_approve(self):
        for rec in self:
            if rec.approval_state != 'submitted':
                raise UserError(_("Must be in submitted state!"))
            rec.write({
                'approval_state': 'supervisor',
                'approved_by_id': self.env.user.id,
                'escalation_deadline': fields.Datetime.now() + timedelta(hours=24),
                'escalation_count': rec.escalation_count,
            })
            rec._sync_status_with_approval()
            if rec.manager_id:
                rec._create_approval_activity(
                    rec.manager_id,
                    _('Manager Approval Required'),
                    _('Please approve work order %s.') % rec.name
                )

    def action_manager_approve(self):
        for rec in self:
            if rec.approval_state != 'supervisor':
                raise UserError(_("Must be supervisor approved!"))
            rec.write({
                'approval_state': 'manager',
                'approved_by_id': self.env.user.id,
                'escalation_deadline': False,
                'escalation_count': rec.escalation_count,
            })
            rec._sync_status_with_approval()

    def action_fully_approve(self):
        for rec in self:
            if rec.approval_state != 'manager':
                raise UserError(_("Must be manager approved!"))
            rec.write({
                'approval_state': 'approved',
                'approved_by_id': self.env.user.id,
            })
            rec._sync_status_with_approval()
            if rec.technician_id and hasattr(rec.technician_id, 'user_id') and rec.technician_id.user_id:
                rec._create_approval_activity(
                    rec.technician_id.user_id,
                    _('Start Work Order'),
                    _('You can start work order %s.') % rec.name
                )

    def action_refuse(self):
        for rec in self:
            rec.write({'approval_state': 'refused'})
            rec._sync_status_with_approval()

    def action_cancel(self):
        for rec in self:
            rec.write({'approval_state': 'cancelled'})
            rec._sync_status_with_approval()

    def action_escalate(self):
        for rec in self:
            if rec.escalation_deadline and fields.Datetime.now() > rec.escalation_deadline:
                if rec.approval_state == 'submitted' and rec.manager_id:
                    rec.write({
                        'approval_state': 'escalated',
                        'escalation_to_id': rec.manager_id.id,
                        'escalation_count': rec.escalation_count + 1,
                        'escalation_deadline': fields.Datetime.now() + timedelta(hours=24),
                    })
                    rec._sync_status_with_approval()
                    rec._create_approval_activity(
                        rec.manager_id,
                        _('Manager Approval Required (Escalated)'),
                        _('Work order %s has been escalated for your approval.') % rec.name
                    )

    @api.model
    def cron_auto_escalate_workorders(self):
        workorders = self.search([
            ('approval_state', 'in', ['submitted', 'supervisor']),
            ('escalation_deadline', '<', fields.Datetime.now())
        ])
        for wo in workorders:
            wo.action_escalate()

    def _copy_job_plan_sections_and_tasks(self):
        self.ensure_one()
        if self.job_plan_id and not self.section_ids:
            for section_template in self.job_plan_id.section_ids.sorted('sequence'):
                section = self.env['maintenance.workorder.section'].create({
                    'workorder_id': self.id,
                    'name': section_template.name,
                    'sequence': section_template.sequence,
                })
                for task_template in section_template.task_ids.sorted('sequence'):
                    self.env['maintenance.workorder.task'].create({
                        'workorder_id': self.id,
                        'section_id': section.id,
                        'name': task_template.name,
                        'sequence': task_template.sequence,
                        'description': task_template.description,
                        'frequency_type': task_template.frequency_type,
                        'is_checklist_item': task_template.is_checklist_item,
                        'is_done': False,
                        'notes': False,
                    })

    def action_start_progress(self):
        for rec in self:
            if rec.status == 'draft' and rec.approval_state == 'approved':
                rec.write({
                    'status': 'in_progress',
                    'actual_start_date': fields.Datetime.now(),
                    'approval_state': 'in_progress',
                })
            else:
                raise UserError(_("Work order must be approved and in 'Draft' state to start progress."))

    def action_complete(self):
        for rec in self:
            if rec.status == 'in_progress':
                # Mark all checklist tasks as completed before completing the workorder
                all_tasks = rec.section_ids.mapped('task_ids') | rec.workorder_task_ids
                checklist_tasks = all_tasks.filtered('is_checklist_item')
                checklist_tasks.write({'is_done': True})
                rec.write({
                    'status': 'done',
                    'actual_end_date': fields.Datetime.now(),
                    'approval_state': 'done',
                })
                if rec.schedule_id and rec.actual_end_date:
                    rec.schedule_id.last_maintenance_date = rec.actual_end_date.date()
            else:
                raise UserError(_("Work order must be 'In Progress' to complete."))

    def action_reset_to_draft(self):
        for rec in self:
            if rec.status != 'draft':
                rec.write({
                    'status': 'draft',
                    'actual_start_date': False,
                    'actual_end_date': False,
                    'approval_state': 'draft',
                })
            else:
                raise UserError(_("Work order is already in draft state."))

    def action_view_picking(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("No parts transfer associated with this work order."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Parts Transfer'),
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_assign_technician(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assign Technician',
            'res_model': 'assign.technician.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_workorder_id': self.id}
        }

    def action_report_downtime(self):
        for rec in self:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Report Downtime'),
                'res_model': 'asset.downtime.reason',
                'view_mode': 'tree,form',
                'target': 'new',
                'context': {'default_asset_id': rec.asset_id.id}
            }