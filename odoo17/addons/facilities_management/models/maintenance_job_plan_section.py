from odoo import models, fields

class MaintenanceJobPlanSection(models.Model):
    _name = 'maintenance.job.plan.section'
    _description = 'Maintenance Job Plan Section'
    _order = 'sequence, id'

    name = fields.Char(
        string='Section Name', required=True, translate=True,
        help="Name of the section (e.g., 'Safety & Documentation')."
    )
    sequence = fields.Integer(
        string='Sequence', default=10,
        help="Order in which the sections appear."
    )
    job_plan_id = fields.Many2one(
        'maintenance.job.plan',
        string='Job Plan',
        required=True,
        ondelete='cascade',
        help="The parent job plan for this section."
    )
    task_ids = fields.One2many(
        'maintenance.job.plan.task', 'section_id',
        string='Tasks', copy=True
    )