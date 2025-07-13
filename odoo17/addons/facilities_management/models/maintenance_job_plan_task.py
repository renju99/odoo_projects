# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MaintenanceJobPlanTask(models.Model):
    _name = 'maintenance.job.plan.task'
    _description = 'Maintenance Job Plan Task'
    _order = 'sequence, name'  # Tasks will be ordered by sequence then name

    job_plan_id = fields.Many2one(
        'maintenance.job.plan', string='Job Plan', required=True, ondelete='cascade',
        help="The Job Plan this task belongs to."
    )
    name = fields.Char(string='Task Description', required=True, translate=True,
                       help="A brief description of the task to be performed.")
    sequence = fields.Integer(string='Sequence', default=10,
                              help="The order in which tasks appear in the job plan.")
    duration = fields.Float(string='Estimated Duration (hours)',
                            help="Estimated time to complete this task in hours.")
    section = fields.Char(string='Section/Area',
                          help="e.g., Safety, HVAC, Electrical, Plumbing.")
    tools_materials = fields.Text(string='Tools/Materials Required',
                                  help="List of tools, parts, or materials needed for this task.")
    responsible_id = fields.Many2one(
        'hr.employee', string='Responsible Personnel (Role)',
        help="The role or type of personnel typically responsible for this task (e.g., FM Technician, Electrician)."
    )
    is_checklist_item = fields.Boolean(string='Checklist Item', default=True,
                                       help="If checked, this task will be copied as a checklist item to the Work Order and must be completed.")

    product_id = fields.Many2one('product.product', string='Required Part')
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)