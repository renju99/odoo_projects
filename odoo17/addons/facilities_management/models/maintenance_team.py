# models/maintenance_team.py
from odoo import fields, models, api

class MaintenanceTeam(models.Model):
    _name = 'maintenance.team'
    _description = 'Maintenance Team'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Team Name", required=True)
    leader_id = fields.Many2one(
        'hr.employee', string="Team Leader",
        domain="[('work_email', '!=', False)]",
        help="The employee responsible for this maintenance team."
    )
    member_ids = fields.Many2many(
        'hr.employee', 'maintenance_team_employee_rel',
        'team_id', 'employee_id', string="Team Members",
        domain="[('work_email', '!=', False)]",
        help="Employees who are part of this maintenance team."
    )
    request_ids = fields.One2many(
        'maintenance.request', 'maintenance_team_id', string="Maintenance Requests"
    )
    workorder_count = fields.Integer(
        string="Number of Requests", compute='_compute_workorder_count'
    )

    @api.depends('request_ids')
    def _compute_workorder_count(self):
        for team in self:
            team.workorder_count = len(team.request_ids)