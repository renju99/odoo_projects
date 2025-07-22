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

    name = fields.Char('Asset Name', required=True, tracking=True)
    asset_tag = fields.Char(string="Asset Tag", tracking=True)
    serial_number = fields.Char(string="Serial Number", tracking=True)
    location = fields.Char(string="Location", compute='_compute_location')
    facility_id = fields.Many2one('facilities.facility', string='Project', required=True, tracking=True)
    asset_code = fields.Char('Asset Code', size=20, tracking=True, copy=False)

    # Timeline History Events for UI
    history_events = fields.Json(string="Asset History Events", compute='_compute_history_events', store=False)
    history_events_display = fields.Text(string="Asset History Timeline", compute='_compute_history_events_display', store=False)
    history_events_html = fields.Html(string="Asset History Timeline", compute='_compute_history_events_html', store=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('maintenance', 'Under Maintenance'),
        ('disposed', 'Disposed'),
    ], string='State', default='draft', tracking=True, required=True)

    def action_activate(self):
        for asset in self:
            asset.state = 'active'

    def action_set_maintenance(self):
        for asset in self:
            asset.state = 'maintenance'

    def action_set_active(self):
        for asset in self:
            asset.state = 'active'

    def action_dispose(self):
        for asset in self:
            asset.state = 'disposed'

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

    # Location Hierarchy Fields
    room_id = fields.Many2one(
        'facilities.room', string='Room',
        tracking=True
    )
    building_id = fields.Many2one(
        'facilities.building', string='Building',
        compute='_compute_building_floor',
        store=True,
        readonly=False
    )
    floor_id = fields.Many2one(
        'facilities.floor', string='Floor',
        compute='_compute_building_floor',
        store=True,
        readonly=False
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

    @api.depends('maintenance_ids', 'depreciation_ids')
    def _compute_history_events(self):
        for asset in self:
            events = []
            # Maintenance events (EXCLUDE preventive work orders)
            for maint in asset.maintenance_ids:
                # If maintenance schedule links to a workorder, and that workorder is NOT preventive, include it
                if hasattr(maint, 'workorder_ids') and maint.workorder_ids:
                    for workorder in maint.workorder_ids:
                        if getattr(workorder, 'work_order_type', None) != 'preventive' and maint.last_maintenance_date:
                            events.append({
                                'date': str(maint.last_maintenance_date),
                                'type': 'maintenance',
                                'name': maint.name,
                                'notes': maint.notes,
                                'details': f"Type: {maint.maintenance_type} ({workorder.work_order_type})"
                            })
                else:
                    # If no workorder connection, just append (legacy)
                    if getattr(maint, 'maintenance_type', None) != 'preventive' and maint.last_maintenance_date:
                        events.append({
                            'date': str(maint.last_maintenance_date),
                            'type': 'maintenance',
                            'name': maint.name,
                            'notes': maint.notes,
                            'details': f"Type: {maint.maintenance_type}"
                        })
            # Depreciation events
            for dep in asset.depreciation_ids:
                events.append({
                    'date': str(dep.depreciation_date),
                    'type': 'depreciation',
                    'name': 'Depreciation',
                    'notes': f"Amount: {dep.depreciation_amount}",
                    'details': f"Value After: {dep.value_after}"
                })
            # Movement events (Stock Picking)
            pickings = self.env['stock.picking'].search([('workorder_id.asset_id', '=', asset.id)])
            for picking in pickings:
                if picking.scheduled_date:
                    events.append({
                        'date': str(picking.scheduled_date),
                        'type': 'movement',
                        'name': picking.name,
                        'notes': f"Transferred: {picking.origin}",
                        'details': f"State: {picking.state}"
                    })
            asset.history_events = sorted(events, key=lambda e: e['date'], reverse=True)

    @api.depends('history_events')
    def _compute_history_events_html(self):
        for asset in self:
            html = "<div class='o_asset_timeline'>"
            for event in asset.history_events or []:
                color = {
                    "maintenance": "#28a745",
                    "depreciation": "#ffc107",
                    "movement": "#17a2b8"
                }.get(event.get("type"), "#007bff")
                html += f"""
                    <div class="o_timeline_event" style="margin-bottom:1em; padding-left:1.5em; position:relative;">
                        <span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:{color}; position:absolute; left:0; top:0.5em;"></span>
                        <strong>{event.get('date', '')}</strong>
                        <span class="badge" style="background:{color}; color:white; margin-left:0.5em;">{event.get('type', '').capitalize()}</span>
                        <div><b>{event.get('name', '')}</b></div>
                        <div>{event.get('notes', '')}</div>
                        <div style="color:#6c757d; font-size:0.85em;">{event.get('details', '')}</div>
                    </div>
                """
            if not (asset.history_events or []):
                html += "<span>No history yet.</span>"
            html += "</div>"
            asset.history_events_html = html

    @api.depends('room_id', 'floor_id', 'building_id')
    def _compute_location(self):
        for asset in self:
            vals = []
            if asset.room_id:
                vals.append(asset.room_id.name)
            if asset.floor_id:
                vals.append(f"Floor {asset.floor_id.name}")
            if asset.building_id:
                vals.append(f"Building {asset.building_id.name}")
            asset.location = ", ".join(vals) if vals else ""