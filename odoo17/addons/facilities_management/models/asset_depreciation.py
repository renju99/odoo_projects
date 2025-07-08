from odoo import models, fields

class AssetDepreciation(models.Model):
    _name = 'facilities.asset.depreciation'
    _description = 'Asset Depreciation Record'

    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True, ondelete='cascade')
    depreciation_date = fields.Date('Depreciation Date', required=True)
    value_before = fields.Float('Value Before Depreciation')
    depreciation_amount = fields.Float('Depreciation Amount')
    value_after = fields.Float('Value After Depreciation')
