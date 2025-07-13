# models/floor.py
from odoo import models, fields, api

class FacilityFloor(models.Model):
    _name = 'facilities.floor'
    _description = 'Facility Floor'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Floor Number/Name', required=True)
    code = fields.Char(string='Floor Code', required=True, copy=False, readonly=True, default='New')
    building_id = fields.Many2one('facilities.building', string='Building', required=True, ondelete='restrict', help="The building this floor belongs to.")
    facility_id = fields.Many2one('facilities.facility', related='building_id.facility_id', string='Facility', store=True, readonly=True, help="The facility this floor indirectly belongs to via its building.")
    manager_id = fields.Many2one('hr.employee', string='Floor Manager')
    active = fields.Boolean(string='Active', default=True)

    # Floor Specific Fields
    level = fields.Integer(string='Level', help="Floor level (e.g., 0 for ground, 1 for first floor).")
    area_sqm = fields.Float(string='Area (sqm)', digits=(10, 2))
    description = fields.Text(string='Description')
    notes = fields.Text(string='Notes')

    # NEW: One2many relationship to Rooms
    room_ids = fields.One2many('facilities.room', 'floor_id', string='Rooms', help="List of rooms on this floor.")
    room_count = fields.Integer(compute='_compute_room_count', string='Number of Rooms', store=True)

    @api.depends('room_ids')
    def _compute_room_count(self):
        for rec in self:
            rec.room_count = len(rec.room_ids)

    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('facilities.floor') or 'New'
        result = super(FacilityFloor, self).create(vals)
        return result

    @api.constrains('building_id')
    def _check_building_id(self):
        for rec in self:
            if not rec.building_id:
                raise fields.ValidationError("A floor must be linked to a Building.")