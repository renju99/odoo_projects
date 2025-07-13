# -*- coding: utf-8 -*-
# /home/ranjith/odoo_projects/odoo17/addons/facilities_management/models/maintenance_workorder_task.py

from odoo import fields, models, api
from odoo.exceptions import ValidationError # Ensure ValidationError is imported

class MaintenanceWorkorderTask(models.Model):
    _name = 'maintenance.workorder.task'
    _description = 'Maintenance Work Order Task'
    _order = 'sequence, id'

    workorder_id = fields.Many2one('maintenance.workorder', string='Work Order', required=True, ondelete='cascade')
    name = fields.Char(string='Task Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    is_done = fields.Boolean(string='Completed', default=False)
    description = fields.Text(string='Instructions')
    notes = fields.Text(string='Technician Notes', help="Notes added by the technician during execution.")
    is_checklist_item = fields.Boolean(string='Checklist Item', default=True,
                                        help="If checked, this task is part of the work order's completion checklist.")

    # NEW FIELDS FOR IMAGES - These are correctly defined here
    before_image = fields.Binary(string="Before Image", attachment=True, help="Image of the asset/area before task execution.")
    before_image_filename = fields.Char(string="Before Image Filename")
    after_image = fields.Binary(string="After Image", attachment=True, help="Image of the asset/area after task execution.")
    after_image_filename = fields.Char(string="After Image Filename")

    # Constraint to ensure 'is_done' can only be changed when WO is in_progress
    @api.constrains('is_done')
    def _check_workorder_status_for_task_done(self):
        for rec in self:
            if rec.is_done and rec.workorder_id.status != 'in_progress':
                # Allow marking done if WO is already done or cancelled, useful if edited after completion/cancellation
                if rec.workorder_id.status not in ('done', 'cancelled'):
                    raise ValidationError(_("Tasks can only be marked as completed when the Work Order is 'In Progress'."))