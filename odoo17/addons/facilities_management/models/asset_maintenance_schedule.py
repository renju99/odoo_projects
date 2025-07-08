from odoo import models, fields, api
from datetime import datetime, timedelta


class AssetMaintenanceSchedule(models.Model):
    _name = 'asset.maintenance.schedule'
    _description = 'Asset Maintenance Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Reference", default="New")
    asset_id = fields.Many2one('facilities.asset', required=True, tracking=True)
    maintenance_date = fields.Date(required=True, tracking=True)
    maintenance_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('predictive', 'Predictive')
    ], required=True)
    status = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='planned', tracking=True)
    is_notified = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('asset.maintenance.schedule') or 'New'
        return super().create(vals)

    def default_get(self, fields):
        res = super().default_get(fields)
        res.update({
            'technician_id': self.env.user.employee_id.id,
        })
        return res

    def send_maintenance_reminder(self):
        """Send reminders for maintenance due in 7 days"""
        tomorrow = fields.Date.today() + timedelta(days=1)
        target_date = tomorrow + timedelta(days=6)  # 7 days from today

        records = self.search([
            ('maintenance_date', '=', target_date),
            ('is_notified', '=', False),
            ('status', '=', 'planned')
        ])

        template = self.env.ref('facilities_management.email_template_maintenance_reminder')
        for record in records:
            template.send_mail(record.id, force_send=True)
            record.is_notified = True