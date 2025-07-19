from odoo import models, fields

class MaintenanceJobPlanTask(models.Model):
    _name = 'maintenance.job.plan.task'
    _description = 'Maintenance Job Plan Task'
    _order = 'section_id, sequence, id'

    section_id = fields.Many2one(
        'maintenance.job.plan.section',
        string='Section',
        required=True,
        ondelete='cascade',
        help="Section to which this task belongs."
    )
    job_plan_id = fields.Many2one(
        'maintenance.job.plan',
        string='Job Plan',
        ondelete='cascade',
        related='section_id.job_plan_id',
        store=True,
        readonly=False,
        help="Job Plan to which this task ultimately belongs (auto-filled from section)."
    )
    name = fields.Char(
        string='Task Name',
        required=True,
        translate=True,
        help="Brief name of the task (e.g., 'Inspect Filters')."
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Order in which the tasks appear within this section."
    )
    description = fields.Text(
        string='Instructions',
        help="Detailed instructions for performing this task."
    )
    is_checklist_item = fields.Boolean(
        string='Checklist Item',
        default=True,
        help="If checked, this task can be marked as completed on a work order."
    )
    duration = fields.Float(
        string='Estimated Duration (hours)',
        help="Estimated time to complete this task in hours."
    )
    tools_materials = fields.Text(
        string='Tools/Materials Required',
        help="List of tools, parts, or materials needed for this task."
    )
    responsible_id = fields.Many2one(
        'hr.employee', string='Responsible Personnel (Role)',
        help="The role or type of personnel typically responsible for this task (e.g., FM Technician, Electrician)."
    )
    product_id = fields.Many2one(
        'product.product', string='Required Part'
    )
    quantity = fields.Float(
        string='Quantity', default=1.0
    )
    uom_id = fields.Many2one(
        'uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True
    )

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