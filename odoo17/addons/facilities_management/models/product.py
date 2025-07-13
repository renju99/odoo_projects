# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    service_policy = fields.Char(compute='_compute_dummy', store=False)
    service_tracking = fields.Selection(
        selection=[('no', 'No Tracking')],
        default='no',
        compute='_compute_dummy',
        store=False
    )

    def _compute_dummy(self):
        for record in self:
            record.service_policy = False
            record.service_tracking = 'no'