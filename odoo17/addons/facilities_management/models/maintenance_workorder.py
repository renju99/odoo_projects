from odoo import models, fields, api

class MaintenanceWorkOrder(models.Model):
    _name = 'maintenance.workorder'
    _description = 'Maintenance Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference',
        required=True,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('maintenance.workorder') or 'New'
    )
    schedule_id = fields.Many2one(
        'asset.maintenance.schedule',
        string="Schedule",
        domain="[('status','=','planned')]",
        ondelete='set null'  # Proper deletion policy
    )
    technician_id = fields.Many2one(
        'hr.employee',
        string="Technician",
        default=lambda self: self._default_technician(),
        tracking=True
    )
    asset_id = fields.Many2one(
        'facilities.asset',
        string="Asset",
        required=True,
        tracking=True
    )
    start_date = fields.Datetime(default=fields.Datetime.now)
    end_date = fields.Datetime()
    status = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)

    def _default_technician(self):
        """Safer default technician implementation"""
        employee = self.env.user.employee_id
        return employee.id if employee else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.workorder') or 'New'
            if not vals.get('technician_id'):
                vals['technician_id'] = self._default_technician()
        return super().create(vals_list)