# models/building.py
from odoo import models, fields, api

class FacilityBuilding(models.Model):
    _name = 'facilities.building'
    _description = 'Facility Building'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Building Name', required=True)
    code = fields.Char(string='Building Code', required=True, copy=False, readonly=True, default='New')
    facility_id = fields.Many2one('facilities.facility', string='Facility/Property', required=True, ondelete='restrict', help="The main facility or property this building belongs to.")
    manager_id = fields.Many2one('hr.employee', string='Building Manager')
    active = fields.Boolean(string='Active', default=True)

    # Building Specific Fields
    address = fields.Char(string='Address', help="Street address of the building if different from facility.")
    building_type = fields.Selection([
        ('office', 'Office'),
        ('residential', 'Residential'),
        ('warehouse', 'Warehouse'),
        ('retail', 'Retail'),
        ('hospital', 'Hospital'),
        ('educational', 'Educational'),
        ('other', 'Other'),
    ], string='Building Type', default='office')
    number_of_floors = fields.Integer(string='Number of Floors')
    total_area_sqm = fields.Float(string='Total Area (sqm)', digits=(10, 2))
    year_constructed = fields.Integer(string='Year Constructed')
    description = fields.Text(string='Description')
    image = fields.Image(string="Building Image", max_width=1024, max_height=1024)

    # NEW: One2many relationship to Floors
    floor_ids = fields.One2many('facilities.floor', 'building_id', string='Floors', help="List of floors within this building.")
    floor_count = fields.Integer(compute='_compute_floor_count', string='Number of Floors', store=True)

    @api.depends('floor_ids')
    def _compute_floor_count(self):
        for rec in self:
            rec.floor_count = len(rec.floor_ids)

    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('facilities.building') or 'New'
        result = super(FacilityBuilding, self).create(vals)
        return result

    @api.constrains('facility_id')
    def _check_facility_id(self):
        for rec in self:
            if not rec.facility_id:
                raise fields.ValidationError("A building must be linked to a Facility.")