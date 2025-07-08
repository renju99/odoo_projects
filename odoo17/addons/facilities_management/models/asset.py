# models/asset.py
from odoo import models, fields, api


class FacilityAsset(models.Model):
    _name = 'facilities.asset'
    _description = 'Facility Asset'
    _rec_name = 'name'

    name = fields.Char('Asset Name', required=True)
    asset_tag = fields.Char(string="Asset Tag")
    serial_number = fields.Char(string="Serial Number")
    facility_id = fields.Many2one('facilities.facility', string='Project', required=True)
    asset_code = fields.Char('Asset Code', size=20)
    maintenance_ids = fields.One2many('facilities.asset.maintenance', 'asset_id', string='Maintenance Records')
    depreciation_ids = fields.One2many('facilities.asset.depreciation', 'asset_id', string='Depreciation Records')
    attachment_ids = fields.Many2many('ir.attachment', string='Documents',
                                    domain="[('res_model','=','facilities.asset')]")

    category_id = fields.Many2one('facilities.asset.category', string='Category')
    purchase_date = fields.Date('Purchase Date')
    condition = fields.Selection([
        ('new', 'New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], default='good', string='Condition')
    responsible_id = fields.Many2one('res.users', string='Responsible Person')
    location = fields.Char('Location')
    warranty_expiration_date = fields.Date('Warranty Expiration Date')
    warranty_status = fields.Selection([
        ('valid', 'Valid'),
        ('expired', 'Expired'),
        ('none', 'No Warranty')
    ], string='Warranty Status', compute='_compute_warranty_status', store=True)
    image_1920 = fields.Image("Image")
    notes = fields.Text('Notes')
    active = fields.Boolean('Active', default=True)

    # New field for dashboard compatibility
    is_enterprise = fields.Boolean(
        string="Enterprise Mode",
        compute='_compute_is_enterprise',
        help="Technical field to check if enterprise features are available"
    )

    @api.depends('warranty_expiration_date')
    def _compute_warranty_status(self):
        today = fields.Date.today()
        for asset in self:
            if not asset.warranty_expiration_date:
                asset.warranty_status = 'none'
            elif asset.warranty_expiration_date >= today:
                asset.warranty_status = 'valid'
            else:
                asset.warranty_status = 'expired'

    def _compute_is_enterprise(self):
        """Check if web_enterprise module is installed"""
        enterprise_installed = self.env['ir.module.module'].search_count([
            ('name', '=', 'web_enterprise'),
            ('state', '=', 'installed')
        ])
        for asset in self:
            asset.is_enterprise = enterprise_installed

    def name_get(self):
        return [(record.id, f"{record.name} [{record.asset_code}]") for record in self]

    def action_open_dashboard(self):
        """Open appropriate dashboard view based on availability of enterprise"""
        self.ensure_one()
        if self.is_enterprise:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Asset Dashboard (Enterprise)',
                'res_model': 'facilities.asset',
                'view_mode': 'dashboard',
                'views': [(False, 'dashboard')],
                'target': 'current',
                'context': dict(self.env.context),
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Asset Dashboard (Community)',
                'res_model': 'facilities.asset',
                'view_mode': 'graph,pivot',
                'views': [
                    (False, 'graph'),
                    (False, 'pivot')
                ],
                'target': 'current',
                'context': dict(self.env.context),
            }