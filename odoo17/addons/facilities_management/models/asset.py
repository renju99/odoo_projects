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
    location = fields.Char('Location', tracking=True)

    # People & Organization
    responsible_id = fields.Many2one('res.users', string='Responsible Person', tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', tracking=True)
    manufacturer_id = fields.Many2one('res.partner', string='Manufacturer', tracking=True)
    service_provider_id = fields.Many2one('res.partner', string='Service Provider', tracking=True)

    # Financial
    purchase_value = fields.Monetary(string='Purchase Value', currency_field='currency_id', tracking=True)
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

    # COMPUTED FIELDS - FIXED
    warranty_status = fields.Selection(
        [
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('none', 'No Warranty')
        ],
        string='Warranty Status',
        compute='_compute_warranty_status',
        store=True
    )

    # Simplified current_value without depreciation dependency
    current_value = fields.Monetary(
        string='Current Value',
        compute='_compute_current_value',
        store=True,
        currency_field='currency_id'
    )

    age_in_years = fields.Float(
        string='Age (Years)',
        compute='_compute_age_in_years',
        store=True
    )

    warranty_days_remaining = fields.Integer(
        string='Warranty Days Remaining',
        compute='_compute_warranty_days_remaining',
        store=True
    )

    # Simplified maintenance_due without dependency on non-existent fields
    maintenance_due = fields.Boolean(
        string='Maintenance Due',
        compute='_compute_maintenance_due',
        store=True
    )

    # CONSTRAINTS
    _sql_constraints = [
        ('unique_asset_code', 'UNIQUE(asset_code)', 'Asset code must be unique!'),
        ('positive_purchase_value', 'CHECK(purchase_value >= 0)', 'Purchase value must be positive!'),
        ('positive_expected_lifespan', 'CHECK(expected_lifespan > 0)', 'Expected lifespan must be positive!'),
    ]

    # COMPUTED METHOD IMPLEMENTATIONS
    @api.depends('barcode')
    def _compute_barcode_image(self):
        for record in self:
            if not qrcode or not record.barcode:
                record.barcode_image = False
            else:
                try:
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(record.barcode)
                    qr.make(fit=True)

                    img = qr.make_image(fill_color="black", back_color="white")
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    record.barcode_image = base64.b64encode(buf.getvalue())
                except Exception as e:
                    record.barcode_image = False

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

    # FIXED: Simplified current_value calculation
    @api.depends('purchase_value', 'purchase_date', 'expected_lifespan')
    def _compute_current_value(self):
        today = fields.Date.today()
        for asset in self:
            if not asset.purchase_value:
                asset.current_value = 0
            elif not asset.purchase_date or not asset.expected_lifespan:
                asset.current_value = asset.purchase_value
            else:
                # Simple straight-line depreciation calculation
                years_passed = (today - asset.purchase_date).days / 365.25
                if years_passed >= asset.expected_lifespan:
                    asset.current_value = 0
                else:
                    annual_depreciation = asset.purchase_value / asset.expected_lifespan
                    total_depreciation = annual_depreciation * years_passed
                    asset.current_value = max(0, asset.purchase_value - total_depreciation)

    @api.depends('purchase_date')
    def _compute_age_in_years(self):
        today = fields.Date.today()
        for asset in self:
            if asset.purchase_date:
                delta = today - asset.purchase_date
                asset.age_in_years = delta.days / 365.25
            else:
                asset.age_in_years = 0

    @api.depends('warranty_expiration_date')
    def _compute_warranty_days_remaining(self):
        today = fields.Date.today()
        for asset in self:
            if asset.warranty_expiration_date:
                delta = asset.warranty_expiration_date - today
                asset.warranty_days_remaining = delta.days
            else:
                asset.warranty_days_remaining = 0

    # FIXED: Simplified maintenance due calculation
    @api.depends('purchase_date', 'condition')
    def _compute_maintenance_due(self):
        for asset in self:
            # Simple logic: assets older than 1 year in poor condition need maintenance
            if asset.purchase_date and asset.condition == 'poor':
                years_old = (fields.Date.today() - asset.purchase_date).days / 365.25
                asset.maintenance_due = years_old > 1
            else:
                asset.maintenance_due = False

    # VALIDATION METHODS
    @api.constrains('purchase_date')
    def _check_purchase_date(self):
        for asset in self:
            if asset.purchase_date and asset.purchase_date > fields.Date.today():
                raise ValidationError("Purchase date cannot be in the future!")

    @api.constrains('warranty_expiration_date', 'purchase_date')
    def _check_warranty_date(self):
        for asset in self:
            if (asset.warranty_expiration_date and asset.purchase_date and
                    asset.warranty_expiration_date < asset.purchase_date):
                raise ValidationError("Warranty expiration date must be after purchase date!")

    @api.constrains('installation_date', 'purchase_date')
    def _check_installation_date(self):
        for asset in self:
            if (asset.installation_date and asset.purchase_date and
                    asset.installation_date < asset.purchase_date):
                raise ValidationError("Installation date must be after purchase date!")

    # CRUD OPERATIONS
    @api.model
    def create(self, vals):
        # Generate barcode if not provided
        if not vals.get('barcode'):
            vals['barcode'] = self._generate_barcode()

        # Generate asset code if not provided
        if not vals.get('asset_code'):
            vals['asset_code'] = self.env['ir.sequence'].next_by_code('facilities.asset.code') or '/'

        rec = super().create(vals)
        rec._compute_barcode_image()
        return rec

    def write(self, vals):
        # Track state changes
        if 'state' in vals:
            for record in self:
                old_state = record.state
                record.message_post(
                    body=f"Asset state changed from {dict(record._fields['state'].selection)[old_state]} to {dict(record._fields['state'].selection)[vals['state']]}"
                )

        res = super().write(vals)

        # Regenerate barcode if changed
        if 'barcode' in vals:
            self._compute_barcode_image()

        return res

    # BUSINESS METHODS
    def _generate_barcode(self):
        """Generate a unique barcode for the asset"""
        return self.env['ir.sequence'].next_by_code(
            'facilities.asset.barcode') or f"AST{self.env['ir.sequence'].next_by_code('facilities.asset')}"

    def action_set_to_active(self):
        """Set asset to active state"""
        for record in self:
            if record.state == 'draft':
                record.state = 'active'
                record.message_post(body="Asset activated and ready for use.")
            else:
                raise ValidationError(f"Cannot activate asset from {record.state} state!")

    def action_set_to_maintenance(self):
        """Set asset to maintenance state"""
        for record in self:
            if record.state in ['active', 'draft']:
                record.state = 'maintenance'
                record.message_post(body="Asset sent for maintenance.")
            else:
                raise ValidationError(f"Cannot send asset to maintenance from {record.state} state!")

    def action_set_to_disposed(self):
        """Set asset to disposed state"""
        for record in self:
            record.state = 'disposed'
            record.active = False
            record.message_post(body="Asset disposed.")

    def action_open_dashboard(self):
        """Enhanced dashboard action"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Dashboard - {self.name}',
            'res_model': 'facilities.asset',
            'view_mode': 'graph,pivot',
            'views': [
                (False, 'graph'),
                (False, 'pivot')
            ],
            'target': 'current',
            'domain': [('id', '=', self.id)],
            'context': dict(self.env.context),
        }

    def action_regenerate_qr_code(self):
        """Force QR code regeneration with better error handling"""
        for rec in self:
            if not rec.barcode:
                rec.barcode = rec._generate_barcode()
            rec._compute_barcode_image()
            rec.message_post(body="QR Code regenerated successfully.")

    def name_get(self):
        """Enhanced name display"""
        result = []
        for record in self:
            name = record.name
            if record.asset_code:
                name = f"{name} [{record.asset_code}]"
            if record.state != 'active':
                name = f"{name} ({dict(record._fields['state'].selection)[record.state]})"
            result.append((record.id, name))
        return result

    # REPORTING METHODS
    def get_asset_summary(self):
        """Get summary information for reporting"""
        self.ensure_one()
        return {
            'name': self.name,
            'code': self.asset_code,
            'current_value': self.current_value,
            'age_years': self.age_in_years,
            'condition': dict(self._fields['condition'].selection)[self.condition],
            'state': dict(self._fields['state'].selection)[self.state],
            'warranty_status': dict(self._fields['warranty_status'].selection)[self.warranty_status],
            'maintenance_due': self.maintenance_due,
        }

    @api.model
    def get_assets_by_state(self):
        """Get asset counts grouped by state"""
        return {
            state[0]: self.search_count([('state', '=', state[0])])
            for state in self._fields['state'].selection
        }

    @api.model
    def get_warranty_expiring_soon(self, days=30):
        """Get assets with warranty expiring in the next X days"""
        target_date = fields.Date.today() + timedelta(days=days)
        return self.search([
            ('warranty_expiration_date', '<=', target_date),
            ('warranty_expiration_date', '>=', fields.Date.today()),
            ('state', '!=', 'disposed')
        ])