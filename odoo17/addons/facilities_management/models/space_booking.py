from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FacilitiesSpaceBooking(models.Model):
    _name = 'facilities.space.booking'
    _description = 'Space/Room Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_datetime desc'

    name = fields.Char('Booking Reference', required=True, readonly=True, default=lambda self: _('New'))
    room_id = fields.Many2one('facilities.room', string='Room', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Booked By', default=lambda self: self.env.user, tracking=True)
    start_datetime = fields.Datetime('Start Time', required=True, tracking=True)
    end_datetime = fields.Datetime('End Time', required=True, tracking=True)
    purpose = fields.Char('Purpose', tracking=True)
    attendees = fields.Integer('Number of Attendees')
    notes = fields.Text('Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True, string='Status')

    @api.constrains('start_datetime', 'end_datetime')
    def _check_datetime_validity(self):
        """Check that end datetime is after start datetime"""
        for booking in self:
            if booking.start_datetime and booking.end_datetime:
                if booking.end_datetime <= booking.start_datetime:
                    raise ValidationError(_("End time must be after start time."))

    @api.constrains('room_id', 'start_datetime', 'end_datetime')
    def _check_booking_conflicts(self):
        """Check for overlapping bookings in the same room"""
        for booking in self:
            if not booking.room_id or not booking.start_datetime or not booking.end_datetime:
                continue
            domain = [
                ('room_id', '=', booking.room_id.id),
                ('state', 'in', ['draft', 'confirmed']),
                ('id', '!=', booking.id),
                ('start_datetime', '<', booking.end_datetime),
                ('end_datetime', '>', booking.start_datetime),
            ]
            if self.search_count(domain):
                raise ValidationError(_("This room is already booked for the selected time."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('facilities.space.booking') or _('New')
        records = super().create(vals_list)
        # Send confirmation email for confirmed bookings
        template = self.env.ref('facilities_management.mail_template_space_booking_confirmed', raise_if_not_found=False)
        for rec in records:
            if template and rec.state == 'confirmed':
                template.send_mail(rec.id, force_send=True)
        return records

    def write(self, vals):
        result = super().write(vals)
        # Send confirmation email when booking is confirmed
        if 'state' in vals and vals['state'] == 'confirmed':
            template = self.env.ref('facilities_management.mail_template_space_booking_confirmed', raise_if_not_found=False)
            for rec in self:
                if template:
                    template.send_mail(rec.id, force_send=True)
        return result

    def action_confirm(self):
        """Confirm the booking"""
        self.write({'state': 'confirmed'})

    def action_cancel(self):
        """Cancel the booking"""
        self.write({'state': 'cancelled'})

    def action_draft(self):
        """Reset booking to draft"""
        self.write({'state': 'draft'})