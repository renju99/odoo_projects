from odoo import models, fields, api, _

class MaintenanceJobPlan(models.Model):
    _name = 'maintenance.job.plan'
    _description = 'Maintenance Job Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Job Plan Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False, default=lambda self: _('New'))
    description = fields.Html(string='Description / Guidelines')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    asset_category_ids = fields.Many2many('facilities.asset.category', string='Applicable Asset Categories')
    section_ids = fields.One2many('maintenance.job.plan.section', 'job_plan_id', string='Sections', copy=True)

    # Computed field to get all tasks under this job plan via all sections
    task_ids = fields.One2many(
        'maintenance.job.plan.task',
        'job_plan_id',
        string='All Tasks',
        compute='_compute_task_ids',
        store=False,
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The code of the job plan must be unique!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('maintenance.job.plan') or _('New')
        return super().create(vals_list)

    @api.depends('section_ids.task_ids')
    def _compute_task_ids(self):
        for plan in self:
            plan.task_ids = plan.section_ids.mapped('task_ids')