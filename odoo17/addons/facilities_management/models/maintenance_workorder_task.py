# -*- coding: utf-8 -*-
from odoo import models, fields

class MaintenanceWorkorderTask(models.Model):
    _name = 'maintenance.workorder.task'
    _description = 'Maintenance Work Order Task'
    _order = 'sequence, name'

    workorder_id = fields.Many2one('maintenance.workorder', string='Work Order', required=True, ondelete='cascade')
    name = fields.Char(string='Task Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    # Add other fields as needed