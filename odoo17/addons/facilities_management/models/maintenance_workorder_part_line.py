# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class MaintenanceWorkOrderPartLine(models.Model):
    _name = 'maintenance.workorder.part_line'
    _description = 'Maintenance Work Order Part Line'

    workorder_id = fields.Many2one('maintenance.workorder', string='Work Order', required=True, ondelete='cascade')
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain=[('type', 'in', ['product', 'consu'])],
        context={'default_type': 'product'}
    )
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)
    notes = fields.Char(string='Notes')

    # NEW FIELD TO SHOW IN-HAND STOCK
    product_qty_in_hand = fields.Float(
        string='Qty On Hand',
        related='product_id.free_qty', # Use free_qty for unreserved quantity
        readonly=True,
        help="Quantity of this product available in stock (unreserved)."
    )


    @api.constrains('quantity')
    def _check_positive_quantity(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(_('Quantity must be positive for parts used.'))

    @api.constrains('workorder_id')
    def _check_workorder_status_for_parts(self):
        for record in self:
            if record.workorder_id and record.workorder_id.status != 'in_progress':
                raise ValidationError(_(
                    "Parts can only be added or modified for a Work Order that is 'In Progress'. "
                    "Current status of Work Order '%s' is '%s'."
                ) % (record.workorder_id.name, record.workorder_id.status.replace('_', ' ').title()))

    @api.constrains('product_id', 'quantity')
    def _check_available_quantity(self):
        for record in self:
            if record.product_id and record.product_id.type == 'product' and record.quantity > 0:
                # Using free_qty for the constraint as well, for consistency with the new displayed field
                if record.quantity > record.product_id.free_qty:
                    raise ValidationError(_(
                        "Not enough quantity available for product '%s'.\n"
                        "Requested: %s %s, Available (On Hand): %s %s."
                    ) % (
                        record.product_id.display_name,
                        record.quantity, record.uom_id.name,
                        record.product_id.free_qty, record.uom_id.name
                    ))