from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class MaintenanceWorkOrder(models.Model):
    _name = 'maintenance.workorder'
    _description = 'Maintenance Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    SERVICE_TYPE_SELECTION = [
        ('maintenance', 'Maintenance'),
        ('cleaning', 'Cleaning'),
        ('security', 'Security'),
        ('esg', 'ESG Compliance'),
        ('hse', 'HSE Incident')
    ]

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

    description = fields.Text(string='Work Order Description')
    work_done = fields.Text(string='Work Done Notes')
    parts_used_ids = fields.One2many('maintenance.workorder.part_line', 'workorder_id', string='Parts Used')
    picking_id = fields.Many2one('stock.picking', string='Parts Transfer', copy=False,
                                 help="The internal transfer for parts issued for this work order.")
    picking_count = fields.Integer(compute='_compute_picking_count', string='Transfers')
    has_parts = fields.Boolean(compute='_compute_has_parts', store=True, help="Indicates if this work order has parts lines.")

    # --- ADDED FIELDS ---
    service_type = fields.Selection(
        SERVICE_TYPE_SELECTION,
        string="Service Type",
        tracking=True,
        help="Department/Service this work order belongs to."
    )
    maintenance_team_id = fields.Many2one(
        'maintenance.team', string="Maintenance Team",
        help="The team assigned to handle this work order."
    )
    # --------------------

    # Hierarchical Sections
    section_ids = fields.One2many(
        'maintenance.workorder.section', 'workorder_id',
        string='Sections'
    )

    # Flat task list (legacy support)
    workorder_task_ids = fields.One2many('maintenance.workorder.task', 'workorder_id', string='Tasks', copy=True)

    all_tasks_completed = fields.Boolean(compute='_compute_all_tasks_completed', store=False,
                                         help="Indicates if all checklist tasks are marked as completed.")

    job_plan_id = fields.Many2one('maintenance.job.plan', string='Job Plan',
                                  help="The job plan linked to this work order, providing detailed tasks.")

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.workorder') or _('New')
        records = super().create(vals_list)
        for rec in records:
            if rec.job_plan_id:
                rec._copy_job_plan_sections_and_tasks()
        return records

    def _copy_job_plan_sections_and_tasks(self):
        """Copy sections & tasks from job plan to work order."""
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

    def action_cancel(self):
        for rec in self:
            if rec.status not in ('done', 'cancelled'):
                rec.write({'status': 'cancelled'})
            else:
                raise UserError(_("Cannot cancel a completed or already cancelled work order."))

    def action_start_progress(self):
        for rec in self:
            if rec.status == 'draft':
                rec.write({
                    'status': 'in_progress',
                    'actual_start_date': fields.Datetime.now(),
                })
            else:
                raise UserError(_("Work order must be in 'Draft' state to start progress."))

    def action_complete(self):
        for rec in self:
            if rec.status == 'in_progress':
                if not rec.all_tasks_completed:
                    raise UserError(_("Cannot complete work order: Not all checklist tasks are marked as completed."))
                rec.write({
                    'status': 'done',
                    'actual_end_date': fields.Datetime.now(),
                })
                if rec.schedule_id and rec.actual_end_date:
                    rec.schedule_id.last_maintenance_date = rec.actual_end_date.date()
            else:
                raise UserError(_("Work order must be 'In Progress' to complete."))

    def action_reset_to_draft(self):
        for rec in self:
            if rec.status in ('done', 'cancelled'):
                rec.write({
                    'status': 'draft',
                    'actual_start_date': False,
                    'actual_end_date': False,
                })
            else:
                raise UserError(_("Only completed or cancelled work orders can be reset to draft."))

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
        for rec in self:
            # open wizard (recommended) or assign current user as technician for demo
            if not rec.technician_id:
                rec.technician_id = self.env.user.employee_id.id
            else:
                raise UserError(_("Technician already assigned. Use form view to change."))

    def action_report_downtime(self):
        for rec in self:
            # Open downtime wizard or show notification (demo)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Report Downtime'),
                'res_model': 'asset.downtime.reason',
                'view_mode': 'tree,form',
                'target': 'new',
                'context': {'default_asset_id': rec.asset_id.id}
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