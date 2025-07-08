from odoo import models, fields

class Facility(models.Model):
    _name = 'facilities.facility'
    _description = 'Physical Facility Record'

    name = fields.Char('Facility Name', required=True, help="e.g., Main Office Building")
    code = fields.Char('Facility Code', default='FAC-000')
    manager_id = fields.Many2one('res.users', string='Facility Manager')
    active = fields.Boolean(default=True)