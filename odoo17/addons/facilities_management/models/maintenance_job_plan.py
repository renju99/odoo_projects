# /home/ranjith/odoo_projects/odoo17/addons/facilities_management/models/maintenance_job_plan.py

from odoo import fields, models, api, _

class MaintenanceJobPlan(models.Model):
    _name = 'maintenance.job.plan'
    _description = 'Maintenance Job Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Job Plan Name', required=True, translate=True,
                       help="Name or title of the job plan (e.g., 'FCU Monthly Check')")
    code = fields.Char(string='Code', copy=False, default=lambda self: _('New'),
                       help="Unique code for the job plan.")
    description = fields.Html(string='Description / Guidelines',
                               help="Detailed description and general guidelines for this job plan. "
                                    "This can include safety precautions, overall scope, etc.")
    active = fields.Boolean(default=True,
                            help="If unchecked, the job plan will be archived and hidden.")
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    asset_category_ids = fields.Many2many('facilities.asset.category',
                                          string='Applicable Asset Categories',
                                          help="Specify asset categories this job plan is relevant for. "
                                               "Leave empty to apply to all asset categories.")

    task_ids = fields.One2many('maintenance.job.plan.task', 'job_plan_id', string='Tasks', copy=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The code of the job plan must be unique!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('maintenance.job.plan') or _('New')
        return super().create(vals_list)


class MaintenanceJobPlanTask(models.Model):
    _name = 'maintenance.job.plan.task'
    _description = 'Maintenance Job Plan Task'
    _order = 'sequence, id'

    job_plan_id = fields.Many2one('maintenance.job.plan', string='Job Plan', required=True, ondelete='cascade')
    name = fields.Char(string='Task Name', required=True, translate=True,
                       help="Brief name of the task (e.g., 'Inspect Filters').")
    sequence = fields.Integer(string='Sequence', default=10,
                              help="Order in which the tasks appear.")
    description = fields.Text(string='Instructions',
                              help="Detailed instructions for performing this task.")
    frequency_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('biannual', 'Biannual'),
        ('annual', 'Annual'),
        ('ad_hoc', 'Ad-hoc / As Needed'),
        ('other', 'Other'),
    ], string='Recommended Frequency', default='ad_hoc',
       help="Recommended frequency for this specific task within the job plan.")
    is_checklist_item = fields.Boolean(string='Checklist Item', default=True,
                                        help="If checked, this task can be marked as completed on a work order.")