# -*- coding: utf-8 -*-
from odoo import fields, models

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_technician = fields.Boolean(string="Is Technician", default=False,
                                   help="Check this box if the employee is a technician eligible for work orders.")