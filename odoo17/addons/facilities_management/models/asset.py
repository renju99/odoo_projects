from odoo import models, fields, api
import base64
import io

try:
    import qrcode
except ImportError:
    qrcode = None

class FacilityAsset(models.Model):
    _name = 'facilities.asset'
    _description = 'Facility Asset'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Asset Name', required=True, tracking=True)
    asset_tag = fields.Char(string="Asset Tag", tracking=True)
    serial_number = fields.Char(string="Serial Number", tracking=True)
    facility_id = fields.Many2one('facilities.facility', string='Project', required=True, tracking=True)
    asset_code = fields.Char('Asset Code', size=20, tracking=True)
    maintenance_ids = fields.One2many('asset.maintenance.schedule', 'asset_id', string='Maintenance Schedules')
    depreciation_ids = fields.One2many('facilities.asset.depreciation', 'asset_id', string='Depreciation Records')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Documents',
        domain="[('res_model','=','facilities.asset')]"
    )
    category_id = fields.Many2one('facilities.asset.category', string='Category', tracking=True)
    purchase_date = fields.Date('Purchase Date', tracking=True)
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
    responsible_id = fields.Many2one('res.users', string='Responsible Person', tracking=True)
    location = fields.Char('Location', tracking=True)
    warranty_expiration_date = fields.Date('Warranty Expiration Date', tracking=True)
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
    image_1920 = fields.Image("Image")
    notes = fields.Text('Notes')
    active = fields.Boolean('Active', default=True)
    manufacturer_id = fields.Many2one('res.partner', string='Manufacturer', tracking=True)
    model_number = fields.Char(string='Model Number', tracking=True)
    installation_date = fields.Date(string='Installation Date', tracking=True)
    purchase_value = fields.Monetary(string='Purchase Value', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    expected_lifespan = fields.Integer(string='Expected Lifespan (Years)', tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', tracking=True)
    service_provider_id = fields.Many2one('res.partner', string='Service Provider', tracking=True)

    barcode = fields.Char('Barcode', copy=False, index=True, tracking=True)
    barcode_image = fields.Image(
        "QR Code Image",
        compute='_compute_barcode_image',
        store=True,
        attachment=True,
        max_width=256,
        max_height=256
    )

    @api.depends('barcode')
    def _compute_barcode_image(self):
        for record in self:
            if not qrcode or not record.barcode:
                record.barcode_image = False
            else:
                try:
                    qr = qrcode.make(record.barcode)
                    buf = io.BytesIO()
                    qr.save(buf, format='PNG')
                    record.barcode_image = base64.b64encode(buf.getvalue())
                except Exception:
                    record.barcode_image = False

    @api.model
    def create(self, vals):
        if not vals.get('barcode'):
            vals['barcode'] = self.env['ir.sequence'].next_by_code('facilities.asset.barcode') or '/'
        rec = super().create(vals)
        rec._compute_barcode_image()
        return rec

    def write(self, vals):
        res = super().write(vals)
        if 'barcode' in vals:
            self._compute_barcode_image()
        return res

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

    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.asset_code:
                name = f"{name} [{record.asset_code}]"
            result.append((record.id, name))
        return result

    def action_open_dashboard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Asset Dashboard',
            'res_model': 'facilities.asset',
            'view_mode': 'graph,pivot',
            'views': [
                (False, 'graph'),
                (False, 'pivot')
            ],
            'target': 'current',
            'context': dict(self.env.context),
        }

    def action_regenerate_qr_code(self):
        """Call this method (add a smart button if needed) to force QR code regeneration."""
        for rec in self:
            rec._compute_barcode_image()