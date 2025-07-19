from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class MaintenanceWorkorderTask(models.Model):
    _name = 'maintenance.workorder.task'
    _description = 'Maintenance Work Order Task'
    _order = 'section_id, sequence, id'

    workorder_id = fields.Many2one('maintenance.workorder', string='Work Order', required=True, ondelete='cascade')
    section_id = fields.Many2one(
        'maintenance.workorder.section',
        string='Section',
        ondelete='cascade'
    )
    name = fields.Char(string='Task Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    is_done = fields.Boolean(string='Completed', default=False)
    description = fields.Text(string='Instructions')
    notes = fields.Text(string='Technician Notes', help="Notes added by the technician during execution.")
    is_checklist_item = fields.Boolean(
        string='Checklist Item',
        default=True,
        help="If checked, this task is part of the work order's completion checklist."
    )
    before_image = fields.Binary(string="Before Image", attachment=True, help="Image of the asset/area before task execution.")
    before_image_filename = fields.Char(string="Before Image Filename")
    after_image = fields.Binary(string="After Image", attachment=True, help="Image of the asset/area after task execution.")
    after_image_filename = fields.Char(string="After Image Filename")
    duration = fields.Float(string='Estimated Duration (hours)')
    tools_materials = fields.Text(string='Tools/Materials Required')
    responsible_id = fields.Many2one('hr.employee', string='Responsible Personnel (Role)')
    product_id = fields.Many2one('product.product', string='Required Part')
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    frequency_type = fields.Selection(
        [
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
        ],
        string='Frequency Type',
        help="How often this task should be performed.",
    )

    @api.constrains('is_done')
    def _check_workorder_status_for_task_done(self):
        for rec in self:
            if rec.is_done and rec.workorder_id.status != 'in_progress':
                if rec.workorder_id.status not in ('done', 'cancelled'):
                    raise ValidationError(_("Tasks can only be marked as completed when the Work Order is 'In Progress'."))