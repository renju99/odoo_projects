from odoo import models, fields

class AssetMaintenance(models.Model):
    _name = 'facilities.asset.maintenance'
    _description = 'Asset Maintenance'

    asset_id = fields.Many2one('facilities.asset', string='Asset', required=True)
    maintenance_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective')
    ], string='Maintenance Type', required=True)
    date_scheduled = fields.Date('Scheduled Date')
    date_performed = fields.Date('Performed Date')
    technician_id = fields.Many2one('res.users', string='Technician')
    notes = fields.Text('Notes')
    status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('done', 'Done')
    ], default='scheduled')
