# -*- coding: utf-8 -*-
from odoo import models, fields

class MaintenanceWorkorderType(models.Model):
    _name = 'maintenance.workorder.type'
    _description = 'Maintenance Workorder Type'
    _order = 'name'

    name = fields.Char(string='Type Name', required=True, translate=True)
    description = fields.Text(string='Description')
    # Add any other fields or methods specific to work order types here