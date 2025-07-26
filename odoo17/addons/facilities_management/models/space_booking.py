from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import re


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
        ('pending', 'Pending Approval'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True, string='Status')

    # Enhanced fields
    booking_type = fields.Selection([
        ('meeting', 'Meeting'),
        ('event', 'Event'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ], string='Booking Type', default='meeting', tracking=True, required=True)

    contact_email = fields.Char('Contact Email', tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', tracking=True)

    # Recurrence fields
    is_recurring = fields.Boolean('Recurring Booking', tracking=True)
    recurrence_rule = fields.Char('Recurrence Rule',
                                  help="iCal-style recurrence rule (e.g., FREQ=WEEKLY;BYDAY=MO,WE,FR)")

    # Attachments
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')

    # External guests
    is_external_guest = fields.Boolean('Has External Guests', tracking=True)
    external_guest_names = fields.Text('External Guest Names', help="List external guest names, one per line")

    # Computed fields
    duration_hours = fields.Float('Duration (Hours)', compute='_compute_duration_hours', store=True)
    is_holiday_conflict = fields.Boolean('Holiday Conflict', compute='_compute_holiday_conflict')
    recurring_display = fields.Char('Recurrence', compute='_compute_recurring_display')

    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration_hours(self):
        for booking in self:
            if booking.start_datetime and booking.end_datetime:
                delta = booking.end_datetime - booking.start_datetime
                booking.duration_hours = delta.total_seconds() / 3600.0
            else:
                booking.duration_hours = 0.0

    @api.depends('start_datetime', 'end_datetime')
    def _compute_holiday_conflict(self):
        for booking in self:
            booking.is_holiday_conflict = False

    @api.depends('is_recurring', 'recurrence_rule')
    def _compute_recurring_display(self):
        for booking in self:
            if booking.is_recurring and booking.recurrence_rule:
                rule = booking.recurrence_rule
                if 'FREQ=DAILY' in rule:
                    booking.recurring_display = 'Daily'
                elif 'FREQ=WEEKLY' in rule:
                    booking.recurring_display = 'Weekly'
                elif 'FREQ=MONTHLY' in rule:
                    booking.recurring_display = 'Monthly'
                else:
                    booking.recurring_display = 'Custom'
            else:
                booking.recurring_display = ''

    @api.constrains('start_datetime', 'end_datetime')
    def _check_datetime_validity(self):
        for booking in self:
            if booking.start_datetime and booking.end_datetime:
                if booking.end_datetime <= booking.start_datetime:
                    raise ValidationError(_("End time must be after start time."))

                if booking.is_holiday_conflict:
                    raise ValidationError(_("Booking conflicts with company holidays."))

    @api.constrains('room_id', 'start_datetime', 'end_datetime')
    def _check_booking_conflicts(self):
        for booking in self:
            if not booking.room_id or not booking.start_datetime or not booking.end_datetime:
                continue
            domain = [
                ('room_id', '=', booking.room_id.id),
                ('state', 'in', ['pending', 'confirmed']),
                ('id', '!=', booking.id),
                ('start_datetime', '<', booking.end_datetime),
                ('end_datetime', '>', booking.start_datetime),
            ]
            if self.search_count(domain):
                raise ValidationError(_("This room is already booked for the selected time."))

    @api.constrains('booking_type', 'department_id')
    def _check_event_department(self):
        for booking in self:
            if booking.booking_type == 'event' and not booking.department_id:
                raise ValidationError(_("Department must be specified for Event bookings."))

    @api.constrains('is_recurring', 'recurrence_rule')
    def _check_recurrence_rule(self):
        for booking in self:
            if booking.is_recurring and booking.recurrence_rule:
                if not self._validate_recurrence_rule(booking.recurrence_rule):
                    raise ValidationError(
                        _("Invalid recurrence rule format. Please use iCal format (e.g., FREQ=WEEKLY;BYDAY=MO,WE,FR)."))

    def _validate_recurrence_rule(self, rule):
        if not rule:
            return False

        if 'FREQ=' not in rule.upper():
            return False

        valid_freq = ['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']
        freq_match = re.search(r'FREQ=([A-Z]+)', rule.upper())
        if freq_match and freq_match.group(1) not in valid_freq:
            return False

        return True

    @api.constrains('contact_email')
    def _check_contact_email(self):
        for booking in self:
            if booking.contact_email:
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, booking.contact_email):
                    raise ValidationError(_("Please enter a valid email address."))

    def create_room_manager_activity(self):
        for booking in self:  # Use 'self' as a recordset in case of multi-create
            manager_employee = booking.room_id.manager_id
            if booking.booking_type == 'event' and booking.state == 'pending' and manager_employee:
                manager_user = manager_employee.user_id
                if manager_user:  # Ensure the employee has a linked Odoo user
                    booking.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=manager_user.id,  # <--- CORRECTED: Use the res.users ID
                        summary='Event booking approval required',
                        note=f'Please review and approve booking {booking.name} for room {booking.room_id.name}.',
                    )
                else:
                    # Optional: Log a warning if manager has no user, or raise error if critical
                    self.env.cr.execute(
                        f"INSERT INTO ir_logging (create_date, create_uid, name, level, message, type, dbname, func, line) VALUES (NOW(), {self.env.uid}, 'facilities.space.booking', 'WARNING', 'Room manager {manager_employee.name} for room {booking.room_id.name} does not have an associated Odoo user. Cannot create approval activity.', 'server', '{self.env.cr.dbname}', 'create_room_manager_activity', '{__name__}.py:L{self._get_linenumber()}');")
                    _logger.warning(
                        "Room manager %s for room %s does not have an associated Odoo user. Cannot create approval activity.",
                        manager_employee.name, booking.room_id.name)

    def schedule_reminder_emails(self):
        for booking in self:
            if booking.state == 'confirmed' and booking.start_datetime:
                reminder_date = booking.start_datetime - timedelta(hours=24)
                if reminder_date > datetime.now():
                    booking.activity_schedule(
                        'mail.mail_activity_data_email',
                        date_deadline=reminder_date.date(),
                        user_id=booking.user_id.id,
                        summary='Booking Reminder',
                        note=f'Reminder: You have a booking tomorrow - {booking.name}',
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('facilities.space.booking') or _('New')

            if vals.get('booking_type') == 'event':
                vals['state'] = 'pending'
            else:
                vals['state'] = 'confirmed'

        records = super().create(vals_list)

        for rec in records:
            # Check if an hr_employee and linked res_users is available for activity creation
            manager_employee = rec.room_id.manager_id
            if rec.booking_type == 'event' and rec.state == 'pending' and manager_employee and manager_employee.user_id:
                rec.create_room_manager_activity()  # This method will now handle fetching user_id correctly

            if rec.state == 'confirmed':
                rec.schedule_reminder_emails()
                template = self.env.ref('facilities_management.mail_template_space_booking_confirmed',
                                        raise_if_not_found=False)
                if template:
                    template.send_mail(rec.id, force_send=True)

        return records

    def write(self, vals):
        old_state = {rec.id: rec.state for rec in self}
        result = super().write(vals)

        for rec in self:
            if vals.get('state') == 'confirmed' and old_state.get(rec.id) != 'confirmed':
                template = self.env.ref('facilities_management.mail_template_space_booking_confirmed',
                                        raise_if_not_found=False)
                if template:
                    template.send_mail(rec.id, force_send=True)
                rec.schedule_reminder_emails()

        return result

    def action_confirm(self):
        for booking in self:
            if booking.booking_type == 'event' and booking.state == 'pending':
                manager_employee = booking.room_id.manager_id

                if not manager_employee:
                    raise ValidationError(_("No room manager assigned to this room. Event booking cannot be approved."))

                manager_user = manager_employee.user_id

                if not manager_user:
                    raise ValidationError(_("The assigned room manager (%s) does not have an associated Odoo user.") % (
                        manager_employee.name))

                if self.env.user.id != manager_user.id:
                    raise ValidationError(_("Only the room manager (%s) can approve this event booking.") % (
                        manager_employee.name))

                # Mark activity as done for the correct user
                activities = self.env['mail.activity'].search([
                    ('res_model', '=', 'facilities.space.booking'),
                    ('res_id', '=', booking.id),
                    ('user_id', '=', manager_user.id),  # <--- CORRECTED: Use the res.users ID here
                    ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                    ('summary', '=', 'Event booking approval required'),
                ])
                activities.action_feedback(feedback='Approved')
                booking.write({'state': 'confirmed'})
            elif booking.state == 'draft':
                booking.write({'state': 'confirmed'})
            elif booking.state == 'pending' and booking.booking_type != 'event':
                booking.write({'state': 'confirmed'})
            else:
                raise ValidationError(_("Booking cannot be confirmed from its current state."))

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_create_recurring_bookings(self):
        for booking in self:
            if not booking.is_recurring or not booking.recurrence_rule:
                continue

            if 'FREQ=WEEKLY' in booking.recurrence_rule.upper():
                current_date = booking.start_datetime
                duration = booking.end_datetime - booking.start_datetime

                for i in range(1, 11):
                    next_start = current_date + timedelta(weeks=i)
                    next_end = next_start + duration

                    existing = self.search([
                        ('room_id', '=', booking.room_id.id),
                        ('start_datetime', '=', next_start),
                        ('end_datetime', '=', next_end),
                    ])

                    if not existing:
                        new_booking_state = 'pending' if booking.booking_type == 'event' else 'confirmed'
                        self.create({
                            'room_id': booking.room_id.id,
                            'user_id': booking.user_id.id,
                            'start_datetime': next_start,
                            'end_datetime': next_end,
                            'purpose': booking.purpose,
                            'attendees': booking.attendees,
                            'notes': booking.notes,
                            'booking_type': booking.booking_type,
                            'contact_email': booking.contact_email,
                            'department_id': booking.department_id.id if booking.department_id else False,
                            'is_external_guest': booking.is_external_guest,
                            'external_guest_names': booking.external_guest_names,
                            'is_recurring': False,
                            'state': new_booking_state,
                        })