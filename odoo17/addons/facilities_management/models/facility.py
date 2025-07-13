# models/facility.py
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class Facility(models.Model):
    _name = 'facilities.facility'
    _description = 'Facility Management'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Basic Information (already there, but with labels for clarity)
    name = fields.Char(string='Facility Name', required=True, help="The official name of the facility or property.")
    code = fields.Char(string='Facility Code', required=True, copy=False, readonly=True, default='New', help="Unique identifier for the facility, often auto-generated.")
    manager_id = fields.Many2one('hr.employee', string='Facility Manager', tracking=True, help="The employee responsible for managing this facility.")
    active = fields.Boolean(string='Active', default=True, help="Set to false to archive the facility.")

    # Location Details
    address = fields.Char(string='Address', help="Street address of the facility.")
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip_code = fields.Char(string='Zip Code')
    country_id = fields.Many2one('res.country', string='Country')
    latitude = fields.Float(string='Latitude', digits=(10, 7), help="Geographical latitude coordinate.")
    longitude = fields.Float(string='Longitude', digits=(10, 7), help="Geographical longitude coordinate.")
    map_link = fields.Char(string='Map Link', help="Link to a map service (e.g., Google Maps) for the facility location.")

    # Property Details
    property_type = fields.Selection([
        ('commercial', 'Commercial'),
        ('residential', 'Residential'),
        ('industrial', 'Industrial'),
        ('retail', 'Retail'),
        ('mixed_use', 'Mixed-Use'),
        ('other', 'Other'),
    ], string='Property Type', default='commercial', help="Categorization of the property.")
    area_sqm = fields.Float(string='Area (sqm)', digits=(10, 2), help="Total area of the facility in square meters.")
    number_of_floors = fields.Integer(string='Number of Floors', help="Total number of floors in the building.")
    year_built = fields.Integer(string='Year Built', help="The year the facility was constructed.")
    last_renovation_date = fields.Date(string='Last Renovation Date', help="Date of the last major renovation.")
    occupancy_status = fields.Selection([
        ('occupied', 'Occupied'),
        ('vacant', 'Vacant'),
        ('under_renovation', 'Under Renovation'),
    ], string='Occupancy Status', default='occupied', help="Current occupancy status of the facility.")
    capacity = fields.Integer(string='Capacity', help="Maximum occupancy or functional capacity of the facility.")

    # Contact & Access Information
    contact_person_id = fields.Many2one('res.partner', string='Primary Contact Person', help="Main contact person associated with this facility (e.g., owner, key tenant).")
    phone = fields.Char(string='Phone Number', help="Primary phone number for the facility.")
    email = fields.Char(string='Email Address', help="Primary email address for the facility.")
    access_instructions = fields.Text(string='Access Instructions', help="Detailed instructions for accessing the facility, e.g., gate codes, key locations.")

    # Utility & Services Information
    electricity_meter_id = fields.Char(string='Electricity Meter ID', help="Identifier for the electricity meter.")
    water_meter_id = fields.Char(string='Water Meter ID', help="Identifier for the water meter.")
    gas_meter_id = fields.Char(string='Gas Meter ID', help="Identifier for the gas meter.")
    internet_provider = fields.Char(string='Internet Provider', help="Main internet service provider.")
    security_system_type = fields.Char(string='Security System Type', help="Description of the security system installed.")

    # Compliance & Documentation
    permit_numbers = fields.Char(string='Permit Numbers', help="Relevant building permits or licenses.")
    inspection_due_date = fields.Date(string='Next Inspection Due Date', help="Date when the next regulatory inspection is due.")
    notes = fields.Text(string='Internal Notes', help="Any additional internal notes or remarks about the facility.")
    documents_ids = fields.Many2many('ir.attachment', string='Facility Documents',
                                    domain="[('res_model','=','facilities.facility')]", help="Attached documents related to the facility (e.g., blueprints, floor plans, certificates).")

    # Relationships (if you want to link to other custom models)
    # tenant_ids = fields.One2many('facilities.tenant', 'facility_id', string='Tenants') # Example if you have a separate Tenant model

    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('facilities.facility') or 'New'
        result = super(Facility, self).create(vals)
        return result

    # No need for _register_hook