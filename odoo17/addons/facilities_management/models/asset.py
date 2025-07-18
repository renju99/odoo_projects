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
    workorder_ids = fields.One2many('maintenance.workorder', 'asset_id', string='Work Orders')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Documents',
        domain="[('res_model','=','facilities.asset')]"
    )
    category_id = fields.Many2one('facilities.asset.category', string='Category', tracking=True)

    # Dates
    purchase_date = fields.Date('Purchase Date', tracking=True)
    installation_date = fields.Date(string='Installation Date', tracking=True)
    warranty_expiration_date = fields.Date('Warranty Expiration Date', tracking=True)
    commissioning_date = fields.Date('Commissioning Date', tracking=True,
                                     help="Date when asset was put into service")

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

    # Performance Related Fields
    performance_ids = fields.One2many('facilities.asset.performance', 'asset_id',
                                      string='Performance Records')
    performance_count = fields.Integer(string='Performance Records',
                                       compute='_compute_performance_count')

    # Default Performance Settings
    default_expected_runtime = fields.Float(string='Default Expected Runtime (Hours/Day)',
                                            default=8.0,
                                            help="Default expected operating hours per day")
    performance_monitoring = fields.Boolean(string='Enable Performance Monitoring',
                                            default=True,
                                            help="Enable automatic performance tracking for this asset")

    # Automated Performance Summary (last 30 days)
    current_availability = fields.Float(string='Current Availability (%)',
                                        compute='_compute_automated_performance_summary',
                                        help="Availability based on work order downtime")
    current_reliability = fields.Float(string='Current Reliability (%)',
                                       compute='_compute_automated_performance_summary',
                                       help="Reliability excluding planned maintenance")
    current_utilization = fields.Float(string='Current Utilization (%)',
                                       compute='_compute_automated_performance_summary',
                                       help="Actual runtime vs expected runtime")
    current_mtbf = fields.Float(string='Current MTBF (Hours)',
                                compute='_compute_automated_performance_summary',
                                help="Mean Time Between Failures")
    current_mttr = fields.Float(string='Current MTTR (Hours)',
                                compute='_compute_automated_performance_summary',
                                help="Mean Time to Repair")
    total_failures_30d = fields.Integer(string='Failures (Last 30 Days)',
                                        compute='_compute_automated_performance_summary')
    total_downtime_30d = fields.Float(string='Total Downtime Hours (Last 30 Days)',
                                      compute='_compute_automated_performance_summary')

    # Work Order Summary
    total_workorders = fields.Integer(string='Total Work Orders',
                                      compute='_compute_workorder_summary')
    pending_workorders = fields.Integer(string='Pending Work Orders',
                                        compute='_compute_workorder_summary')
    completed_workorders = fields.Integer(string='Completed Work Orders',
                                          compute='_compute_workorder_summary')

    # Current Performance Status
    current_performance_status = fields.Selection([
        ('excellent', 'Excellent (≥95%)'),
        ('good', 'Good (80-94%)'),
        ('average', 'Average (60-79%)'),
        ('poor', 'Poor (<60%)')
    ], string='Current Performance Status', compute='_compute_performance_status')

    # Computed Fields for Dashboard
    warranty_status = fields.Selection([
        ('valid', 'Valid'),
        ('expired', 'Expired'),
        ('none', 'No Warranty')
    ], string='Warranty Status', compute='_compute_warranty_status', store=True)

    # Current Value (for dashboard)
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

    # Maintenance Due Status
    maintenance_due = fields.Boolean(string='Maintenance Due', compute='_compute_maintenance_due', store=True)

    # Dashboard compatibility
    is_enterprise = fields.Boolean(
        string="Enterprise Mode",
        compute='_compute_is_enterprise',
        help="Technical field to check if enterprise features are available"
    )

    # Criticality and Risk Assessment
    criticality = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Asset Criticality', default='medium', tracking=True,
        help="Business impact if this asset fails")

    risk_score = fields.Float(string='Risk Score', compute='_compute_risk_score', store=True,
                              help="Calculated risk based on criticality, condition, and failure history")

    # SQL Constraints
    _sql_constraints = [
        ('unique_asset_code', 'UNIQUE(asset_code)', 'Asset code must be unique!'),
        ('positive_purchase_value', 'CHECK(purchase_value >= 0)', 'Purchase value must be positive!'),
        ('positive_expected_lifespan', 'CHECK(expected_lifespan > 0)', 'Expected lifespan must be positive!'),
        ('positive_expected_runtime', 'CHECK(default_expected_runtime > 0)',
         'Default expected runtime must be positive!'),
        ('valid_expected_runtime', 'CHECK(default_expected_runtime <= 24)',
         'Expected runtime cannot exceed 24 hours per day!'),
    ]

    # ============================================================================
    # COMPUTED METHODS
    # ============================================================================

    @api.depends('performance_ids')
    def _compute_performance_count(self):
        for asset in self:
            asset.performance_count = len(asset.performance_ids)

    @api.depends('workorder_ids', 'workorder_ids.status')
    def _compute_workorder_summary(self):
        for asset in self:
            workorders = asset.workorder_ids
            asset.total_workorders = len(workorders)
            asset.pending_workorders = len(workorders.filtered(lambda w: w.status in ['draft', 'in_progress']))
            asset.completed_workorders = len(workorders.filtered(lambda w: w.status == 'done'))

    @api.depends('performance_ids')
    def _compute_automated_performance_summary(self):
        for asset in self:
            thirty_days_ago = fields.Date.today() - timedelta(days=30)
            recent_performance = asset.performance_ids.filtered(
                lambda p: p.date >= thirty_days_ago
            )

            if recent_performance:
                # Calculate averages
                asset.current_availability = sum(recent_performance.mapped('availability')) / len(recent_performance)
                asset.current_reliability = sum(recent_performance.mapped('reliability')) / len(recent_performance)
                asset.current_utilization = sum(recent_performance.mapped('utilization')) / len(recent_performance)
                asset.total_downtime_30d = sum(recent_performance.mapped('downtime_hours'))
                asset.total_failures_30d = sum(recent_performance.mapped('corrective_workorders'))

                # Get latest MTBF and MTTR
                latest_record = recent_performance.sorted('date', reverse=True)[:1]
                if latest_record:
                    asset.current_mtbf = latest_record.mtbf_hours
                    asset.current_mttr = latest_record.mttr_hours
                else:
                    asset.current_mtbf = 0.0
                    asset.current_mttr = 0.0
            else:
                # No recent data - check if we have any work orders to base this on
                recent_workorders = asset.workorder_ids.filtered(
                    lambda w: w.actual_start_date and w.actual_start_date.date() >= thirty_days_ago
                )

                if recent_workorders:
                    # Calculate basic metrics from work orders
                    corrective_wos = recent_workorders.filtered(lambda w: w.work_order_type == 'corrective')
                    total_downtime = sum([
                        (wo.actual_end_date - wo.actual_start_date).total_seconds() / 3600.0
                        for wo in recent_workorders
                        if wo.actual_start_date and wo.actual_end_date
                    ])

                    days_in_period = 30
                    expected_total_runtime = days_in_period * asset.default_expected_runtime
                    actual_runtime = max(0, expected_total_runtime - total_downtime)

                    asset.current_availability = (
                                actual_runtime / expected_total_runtime * 100) if expected_total_runtime > 0 else 100.0
                    asset.current_utilization = asset.current_availability
                    asset.current_reliability = asset.current_availability  # Simplified
                    asset.total_downtime_30d = total_downtime
                    asset.total_failures_30d = len(corrective_wos)
                    asset.current_mtbf = 0.0
                    asset.current_mttr = 0.0
                else:
                    # No data at all
                    asset.current_availability = 100.0
                    asset.current_reliability = 100.0
                    asset.current_utilization = 100.0
                    asset.current_mtbf = 0.0
                    asset.current_mttr = 0.0
                    asset.total_failures_30d = 0
                    asset.total_downtime_30d = 0.0

    @api.depends('current_availability')
    def _compute_performance_status(self):
        for asset in self:
            if asset.current_availability >= 95:
                asset.current_performance_status = 'excellent'
            elif asset.current_availability >= 80:
                asset.current_performance_status = 'good'
            elif asset.current_availability >= 60:
                asset.current_performance_status = 'average'
            else:
                asset.current_performance_status = 'poor'

    @api.depends('criticality', 'condition', 'total_failures_30d', 'current_availability')
    def _compute_risk_score(self):
        for asset in self:
            # Base risk score calculation
            criticality_score = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}.get(asset.criticality, 2)
            condition_score = {'new': 1, 'good': 2, 'fair': 3, 'poor': 4}.get(asset.condition, 2)

            # Failure frequency impact
            failure_score = min(4, asset.total_failures_30d / 2) if asset.total_failures_30d else 1

            # Availability impact
            availability_score = 4 - (asset.current_availability / 25)  # 100% = 0, 0% = 4
            availability_score = max(1, min(4, availability_score))

            # Combined risk score (1-16 scale)
            asset.risk_score = (criticality_score * condition_score * failure_score * availability_score) / 4

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
                asset.warranty_days_remaining = max(0, delta.days)
            else:
                asset.warranty_days_remaining = 0

    @api.depends('maintenance_ids', 'maintenance_ids.next_maintenance_date')
    def _compute_maintenance_due(self):
        today = fields.Date.today()
        for asset in self:
            # Check if any active maintenance schedule is due within 7 days
            due_maintenance = asset.maintenance_ids.filtered(
                lambda m: m.active and m.next_maintenance_date and
                          m.next_maintenance_date <= today + timedelta(days=7)
            )
            asset.maintenance_due = bool(due_maintenance)

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
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(asset.barcode)
                    qr.make(fit=True)

                    img = qr.make_image(fill_color="black", back_color="white")
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    asset.barcode_image = base64.b64encode(buffer.getvalue())
                except Exception:
                    asset.barcode_image = False
            else:
                asset.barcode_image = False

    # ============================================================================
    # CRUD METHODS
    # ============================================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Generate asset code if not provided
            if not vals.get('asset_code'):
                vals['asset_code'] = self.env['ir.sequence'].next_by_code('facilities.asset') or 'AST0000'

            # Generate barcode if not provided
            if not vals.get('barcode'):
                vals['barcode'] = self.env['ir.sequence'].next_by_code('facilities.asset.barcode') or vals.get(
                    'asset_code', 'AST0000')

        return super().create(vals_list)

    def write(self, vals):
        # Auto-generate performance record when asset is activated
        if vals.get('state') == 'active':
            for asset in self:
                if asset.performance_monitoring:
                    self._generate_performance_record_if_missing()

        return super().write(vals)

    def name_get(self):
        return [(record.id, f"{record.name} [{record.asset_code}]") for record in self]

    # ============================================================================
    # PERFORMANCE RELATED ACTIONS
    # ============================================================================

    def action_view_performance(self):
        """View performance records for this asset"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Performance - {self.name}',
            'res_model': 'facilities.asset.performance',
            'view_mode': 'tree,form,graph,pivot',
            'domain': [('asset_id', '=', self.id)],
            'context': {
                'default_asset_id': self.id,
                'search_default_group_by_date': 1,
                'search_default_last_30_days': 1,
            }
        }

    def action_create_performance_record(self):
        """Create a new performance record manually"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'New Performance Record - {self.name}',
            'res_model': 'facilities.asset.performance',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_id': self.id,
                'default_date': fields.Date.context_today(self),
            }
        }

    def action_reliability_dashboard(self):
        """Open reliability dashboard for this asset"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Reliability Dashboard - {self.name}',
            'res_model': 'facilities.asset.performance',
            'view_mode': 'graph,pivot,tree',
            'domain': [('asset_id', '=', self.id)],
            'context': {
                'search_default_last_90_days': 1,
                'graph_mode': 'line',
                'graph_measure': 'availability',
                'graph_groupbys': ['date'],
            }
        }

    def action_mtbf_mttr_analysis(self):
        """Open MTBF/MTTR analysis"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'MTBF/MTTR Analysis - {self.name}',
            'res_model': 'facilities.asset.performance',
            'view_mode': 'graph,pivot,tree',
            'domain': [('asset_id', '=', self.id), ('mtbf_hours', '>', 0)],
            'context': {
                'search_default_last_90_days': 1,
                'graph_mode': 'line',
                'graph_measure': 'mtbf_hours,mttr_hours',
                'graph_groupbys': ['date'],
            }
        }

    # ============================================================================
    # WORK ORDER ACTIONS
    # ============================================================================

    def action_view_workorders(self):
        """View all work orders for this asset"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Work Orders - {self.name}',
            'res_model': 'maintenance.workorder',
            'view_mode': 'tree,form,calendar,graph',
            'domain': [('asset_id', '=', self.id)],
            'context': {
                'default_asset_id': self.id,
                'search_default_group_by_status': 1,
            }
        }

    def action_view_pending_workorders(self):
        """View pending work orders for this asset"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Pending Work Orders - {self.name}',
            'res_model': 'maintenance.workorder',
            'view_mode': 'tree,form',
            'domain': [('asset_id', '=', self.id), ('status', 'in', ['draft', 'in_progress'])],
            'context': {
                'default_asset_id': self.id,
            }
        }

    def action_failure_analysis(self):
        """Analyze failure patterns for this asset"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Failure Analysis - {self.name}',
            'res_model': 'maintenance.workorder',
            'view_mode': 'graph,pivot,tree',
            'domain': [('asset_id', '=', self.id), ('work_order_type', '=', 'corrective')],
            'context': {
                'search_default_group_by_month': 1,
                'graph_mode': 'bar',
                'graph_groupbys': ['create_date:month'],
            }
        }

    # ============================================================================
    # MAINTENANCE ACTIONS
    # ============================================================================

    def action_view_maintenance_schedules(self):
        """View maintenance schedules for this asset"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Maintenance Schedules - {self.name}',
            'res_model': 'asset.maintenance.schedule',
            'view_mode': 'tree,form,calendar',
            'domain': [('asset_id', '=', self.id)],
            'context': {
                'default_asset_id': self.id,
            }
        }

    def action_create_workorder(self):
        """Create a new work order for this asset"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'New Work Order - {self.name}',
            'res_model': 'maintenance.workorder',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_id': self.id,
                'default_work_order_type': 'corrective',
            }
        }

    def action_schedule_maintenance(self):
        """Schedule preventive maintenance"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Schedule Maintenance - {self.name}',
            'res_model': 'maintenance.workorder',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_id': self.id,
                'default_work_order_type': 'preventive',
                'default_start_date': fields.Datetime.now(),
            }
        }

    # ============================================================================
    # FINANCIAL ACTIONS
    # ============================================================================

    def action_view_depreciation(self):
        """View depreciation records for this asset"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Depreciation - {self.name}',
            'res_model': 'facilities.asset.depreciation',
            'view_mode': 'tree,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {
                'default_asset_id': self.id,
            }
        }

    # ============================================================================
    # UTILITY ACTIONS
    # ============================================================================

    def action_generate_qr_code(self):
        """Regenerate QR code for this asset"""
        self.ensure_one()
        if not self.barcode:
            self.barcode = self.env['ir.sequence'].next_by_code('facilities.asset.barcode') or self.asset_code
        self._compute_barcode_image()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'QR Code generated successfully!',
                'type': 'success',
                'sticky': False,
            }
        }

    # ============================================================================
    # STATE MANAGEMENT ACTIONS
    # ============================================================================

    def action_set_active(self):
        """Set asset to active state"""
        self.write({'state': 'active'})
        # Generate initial performance record
        self._generate_performance_record_if_missing()
        return True

    def action_set_maintenance(self):
        """Set asset to maintenance state"""
        self.write({'state': 'maintenance'})
        return True

    def action_set_disposed(self):
        """Set asset to disposed state"""
        self.write({'state': 'disposed'})
        return True

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def _generate_performance_record_if_missing(self):
        """Generate performance record for today if missing"""
        today = fields.Date.today()
        for asset in self:
            if not asset.performance_monitoring:
                continue

            existing_record = self.env['facilities.asset.performance'].search([
                ('asset_id', '=', asset.id),
                ('date', '=', today)
            ])

            if not existing_record:
                self.env['facilities.asset.performance'].create({
                    'asset_id': asset.id,
                    'date': today,
                })

    def get_last_performance_record(self):
        """Get the most recent performance record"""
        self.ensure_one()
        return self.performance_ids.sorted('date', reverse=True)[:1]

    def get_performance_trend(self, days=30):
        """Get performance trend for the last N days"""
        self.ensure_one()
        cutoff_date = fields.Date.today() - timedelta(days=days)
        recent_records = self.performance_ids.filtered(lambda r: r.date >= cutoff_date)

        if len(recent_records) < 2:
            return 'insufficient_data'

        # Calculate trend based on availability percentage
        sorted_records = recent_records.sorted('date')
        first_half = sorted_records[:len(sorted_records) // 2]
        second_half = sorted_records[len(sorted_records) // 2:]

        first_avg = sum(first_half.mapped('availability')) / len(first_half) if first_half else 0
        second_avg = sum(second_half.mapped('availability')) / len(second_half) if second_half else 0

        if second_avg > first_avg + 5:
            return 'improving'
        elif second_avg < first_avg - 5:
            return 'declining'
        else:
            return 'stable'

    def calculate_overall_equipment_effectiveness(self, start_date=None, end_date=None):
        """Calculate Overall Equipment Effectiveness (OEE) for a date range"""
        self.ensure_one()

        if not start_date:
            start_date = fields.Date.today() - timedelta(days=30)
        if not end_date:
            end_date = fields.Date.today()

        performance_records = self.performance_ids.filtered(
            lambda r: start_date <= r.date <= end_date
        )

        if not performance_records:
            return {
                'availability': 0.0,
                'performance': 0.0,
                'quality': 100.0,  # Assume 100% quality if not tracked
                'oee': 0.0
            }

        # Calculate averages
        avg_availability = sum(performance_records.mapped('availability')) / len(performance_records)
        avg_performance = sum(performance_records.mapped('utilization')) / len(performance_records)
        quality = 100.0  # Placeholder - implement quality tracking as needed

        # OEE = Availability × Performance × Quality (all as percentages)
        oee = (avg_availability * avg_performance * quality) / 10000  # Divide by 100^2 to get percentage

        return {
            'availability': avg_availability,
            'performance': avg_performance,
            'quality': quality,
            'oee': oee
        }

    def get_maintenance_cost_summary(self, days=30):
        """Get maintenance cost summary for specified period"""
        self.ensure_one()
        cutoff_date = fields.Date.today() - timedelta(days=days)

        workorders = self.workorder_ids.filtered(
            lambda w: w.actual_start_date and w.actual_start_date.date() >= cutoff_date
        )

        total_cost = 0.0
        for wo in workorders:
            # Calculate cost from parts and labor
            parts_cost = sum(wo.parts_used_ids.mapped(lambda p: p.quantity * (p.product_id.standard_price or 0)))
            # Add labor cost calculation here if you have hourly rates
            labor_cost = 0.0  # Placeholder
            total_cost += parts_cost + labor_cost

        return {
            'total_cost': total_cost,
            'workorder_count': len(workorders),
            'average_cost_per_workorder': total_cost / len(workorders) if workorders else 0,
        }

    # ============================================================================
    # VALIDATION METHODS
    # ============================================================================

    @api.constrains('default_expected_runtime')
    def _check_expected_runtime(self):
        for asset in self:
            if asset.default_expected_runtime <= 0:
                raise ValidationError("Default expected runtime must be greater than 0 hours.")
            if asset.default_expected_runtime > 24:
                raise ValidationError("Default expected runtime cannot exceed 24 hours per day.")

    @api.constrains('purchase_date', 'installation_date', 'commissioning_date')
    def _check_dates(self):
        for asset in self:
            if asset.purchase_date and asset.installation_date:
                if asset.installation_date < asset.purchase_date:
                    raise ValidationError("Installation date cannot be before purchase date.")

            if asset.installation_date and asset.commissioning_date:
                if asset.commissioning_date < asset.installation_date:
                    raise ValidationError("Commissioning date cannot be before installation date.")

    @api.constrains('expected_lifespan')
    def _check_lifespan(self):
        for asset in self:
            if asset.expected_lifespan and asset.expected_lifespan <= 0:
                raise ValidationError("Expected lifespan must be positive.")
            if asset.expected_lifespan and asset.expected_lifespan > 100:
                raise ValidationError("Expected lifespan seems unrealistic (>100 years).")