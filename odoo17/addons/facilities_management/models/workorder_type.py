# models/workorder_type.py

from odoo import models, fields

class WorkorderType(models.Model):
    _name = 'workorder.type'
    _description = 'Type of Maintenance Work Order'
    _order = 'name'

    name = fields.Char(string='Type Name', required=True, help="A descriptive name for the work order type (e.g., 'Routine Inspection', 'Emergency Repair').")
    description = fields.Text(string='Description', help="Detailed description of this work order type.")

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The work order type name must be unique!'),
    ]