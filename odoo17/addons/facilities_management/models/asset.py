from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64
import io
from datetime import date, datetime, timedelta

try:
    import qrcode
except ImportError:
    qrcode = None


class FacilityAsset(models.Model):
    _name = 'facilities.asset'
    _description = 'Facility Asset'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, asset_code'

    # Basic Information
    name = fields.Char('Asset Name', required=True, tracking=True)
    asset_tag = fields.Char(string="Asset Tag", tracking=True)
    serial_number = fields.Char(string="Serial Number", tracking=True)
    facility_id = fields.Many2one('facilities.facility', string='Project', required=True, tracking=True)
    asset_code = fields.Char('Asset Code', size=20, tracking=True, copy=False)

    # State Management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('maintenance', 'Under Maintenance'),
        ('disposed', 'Disposed'),
    ], string='State', default='draft', tracking=True, required=True)

    # Relationships
    maintenance_ids = fields.One2many('asset.maintenance.schedule', 'asset_id', string='Maintenance Schedules')
    depreciation_ids = fields.One2many('facilities.asset.depreciation', 'asset_id', string='Depreciation Records')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Documents',
        domain="[('res_model','=','facilities.asset')]"
    )
    category_id = fields.Many2one('facilities.asset.category', string='Category', tracking=True)

    # Dates
    purchase_date = fields.Date('Purchase Date', tracking=True)
    installation_date = fields.Date(string='Installation Date', tracking=True)
    warranty_expiration_date = fields.Date('Warranty Expiration Date', tracking=True)

    # Physical Properties
    condition = fields.Selection(
        [
            ('new', 'New'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor'),
        ],
        default='good',
        string='Condition',
        tracking=True
    )
    # location = fields.Char('Location', tracking=True)  # REMOVED

    # Location Hierarchy Fields
    room_id = fields.Many2one(
        'facilities.room', string='Room',
        tracking=True
    )
    building_id = fields.Many2one(
        'facilities.building', string='Building',
        compute='_compute_building_floor',
        store=True,
        readonly=False # allow override if needed
    )
    floor_id = fields.Many2one(
        'facilities.floor', string='Floor',
        compute='_compute_building_floor',
        store=True,
        readonly=False # allow override if needed
    )

    @api.depends('room_id')
    def _compute_building_floor(self):
        for asset in self:
            asset.building_id = asset.room_id.building_id if asset.room_id and asset.room_id.building_id else False
            asset.floor_id = asset.room_id.floor_id if asset.room_id and asset.room_id.floor_id else False

    # People & Organization
    responsible_id = fields.Many2one('res.users', string='Responsible Person', tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', tracking=True)
    manufacturer_id = fields.Many2one('res.partner', string='Manufacturer', tracking=True)
    service_provider_id = fields.Many2one('res.partner', string='Service Provider', tracking=True)

    # Financial
    purchase_value = fields.Monetary(string='Purchase Value', currency_field='currency_id', tracking=True)
    current_value = fields.Monetary(string='Current Value', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    # Technical Details
    model_number = fields.Char(string='Model Number', tracking=True)
    expected_lifespan = fields.Integer(string='Expected Lifespan (Years)', tracking=True)

    # Media & Documentation
    image_1920 = fields.Image("Image")
    notes = fields.Text('Notes')
    active = fields.Boolean('Active', default=True)

    # Barcode System
    barcode = fields.Char('Barcode', copy=False, index=True, tracking=True)
    barcode_image = fields.Image(
        "QR Code Image",
        compute='_compute_barcode_image',
        store=True,
        attachment=True,
        max_width=256,
        max_height=256
    )

    # COMPUTED FIELDS
    warranty_status = fields.Selection(
        [
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('none', 'No Warranty')
        ],
        string='Warranty Status',
        compute='_compute_warranty_status',
        store=True,
        tracking=True
    )

    maintenance_due = fields.Boolean(
        string='Maintenance Due',
        compute='_compute_maintenance_due',
        store=True
    )

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

    @api.depends('maintenance_ids.next_maintenance_date')
    def _compute_maintenance_due(self):
        today = fields.Date.today()
        for asset in self:
            due_maintenances = asset.maintenance_ids.filtered(
                lambda m: m.active and m.next_maintenance_date and m.next_maintenance_date <= today
            )
            asset.maintenance_due = bool(due_maintenances)

    def _compute_is_enterprise(self):
        """Check if web_enterprise module is installed"""
        enterprise_installed = self.env['ir.module.module'].search_count([
            ('name', '=', 'web_enterprise'),
            ('state', '=', 'installed')
        ])
        for asset in self:
            asset.is_enterprise = enterprise_installed

    @api.depends('barcode')
    def _compute_barcode_image(self):
        for asset in self:
            if asset.barcode and qrcode:
                try:
                    qr = qrcode.QRCode(version=1, box_size=4, border=1)
                    qr.add_data(asset.barcode)
                    qr.make(fit=True)
                    img = qr.make_image()

                    # Convert to base64
                    buffered = io.BytesIO()
                    img.save(buffered, format="PNG")
                    img_str = base64.b64encode(buffered.getvalue())
                    asset.barcode_image = img_str
                except Exception:
                    asset.barcode_image = False
            else:
                asset.barcode_image = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('asset_code'):
                vals['asset_code'] = self.env['ir.sequence'].next_by_code('facilities.asset') or 'AS0000'
            if not vals.get('barcode'):
                vals['barcode'] = self.env['ir.sequence'].next_by_code('facilities.asset.barcode') or 'AS0000'
        return super().create(vals_list)

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
                'view_mode': 'kanban,graph,pivot',
                'views': [(False, 'kanban'), (False, 'graph'), (False, 'pivot')],
                'target': 'current',
                'context': dict(self.env.context),
            }