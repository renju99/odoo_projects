# models/room.py
from odoo import models, fields, api

class FacilityRoom(models.Model):
    _name = 'facilities.room'
    _description = 'Facility Room'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Room Name/Number', required=True)
    code = fields.Char(string='Room Code', required=True, copy=False, readonly=True, default='New')
    floor_id = fields.Many2one('facilities.floor', string='Floor', required=True, ondelete='restrict', help="The floor this room is located on.")
    building_id = fields.Many2one('facilities.building', related='floor_id.building_id', string='Building', store=True, readonly=True, help="The building this room indirectly belongs to.")
    facility_id = fields.Many2one('facilities.facility', related='floor_id.building_id.facility_id', string='Facility', store=True, readonly=True, help="The facility this room indirectly belongs to.")
    manager_id = fields.Many2one('hr.employee', string='Room Manager')
    active = fields.Boolean(string='Active', default=True)

    # Room Specific Fields
    room_type = fields.Selection([
        ('office', 'Office'),
        ('meeting_room', 'Meeting Room'),
        ('restroom', 'Restroom'),
        ('kitchen', 'Kitchen'),
        ('storage', 'Storage'),
        ('utility', 'Utility Room'),
        ('classroom', 'Classroom'),
        ('laboratory', 'Laboratory'),
        ('other', 'Other'),
    ], string='Room Type', default='office')
    capacity = fields.Integer(string='Capacity', help="Maximum occupancy of the room.")
    area_sqm = fields.Float(string='Area (sqm)', digits=(10, 2))
    usage = fields.Text(string='Current Usage/Purpose')
    notes = fields.Text(string='Notes')

    # Many2many example if rooms have specific equipment categories
    # equipment_category_ids = fields.Many2many('maintenance.equipment.category', string='Equipment Categories')

    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('facilities.room') or 'New'
        result = super(FacilityRoom, self).create(vals)
        return result

    @api.constrains('floor_id')
    def _check_floor_id(self):
        for rec in self:
            if not rec.floor_id:
                raise fields.ValidationError("A room must be linked to a Floor.")