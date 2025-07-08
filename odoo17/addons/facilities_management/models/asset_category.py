from odoo import models, fields

class AssetCategory(models.Model):
    _name = 'facilities.asset.category'
    _description = 'Asset Category'

    name = fields.Char('Category Name', required=True)
    description = fields.Text('Description')
    active = fields.Boolean('Active', default=True)  # Add this line
