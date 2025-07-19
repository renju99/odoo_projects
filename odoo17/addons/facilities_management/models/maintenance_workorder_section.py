from odoo import models, fields

class MaintenanceWorkorderSection(models.Model):
    _name = 'maintenance.workorder.section'
    _description = 'Work Order Section'
    _order = 'sequence, id'

    name = fields.Char(string='Section Name', required=True, readonly=True)
    sequence = fields.Integer(string='Sequence', default=10, readonly=True)
    workorder_id = fields.Many2one('maintenance.workorder', string='Work Order', required=True, ondelete='cascade')
    task_ids = fields.One2many('maintenance.workorder.task', 'section_id', string='Tasks')