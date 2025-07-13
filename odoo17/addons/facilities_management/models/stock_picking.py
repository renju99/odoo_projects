# /home/ranjith/odoo_projects/odoo17/addons/facilities_management/models/stock_picking.py
from odoo import fields, models, api, _

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    workorder_id = fields.Many2one(
        'maintenance.workorder',
        string='Maintenance Work Order',
        help="Link to the Maintenance Work Order that generated this stock transfer.",
        copy=False # Do not copy this link when duplicating a picking
    )

class StockMove(models.Model):
    _inherit = 'stock.move'

    workorder_id = fields.Many2one('maintenance.workorder', string='Maintenance Work Order',
                                   help='Related Maintenance Work Order', copy=False)