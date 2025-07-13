# models/maintenance_request.py
from odoo import fields, models, api
from odoo.exceptions import UserError
from datetime import datetime


class MaintenanceRequest(models.Model):
    # CORRECTED LINE: Inherit from maintenance.request and mail.thread, mail.activity.mixin
    _inherit = ['maintenance.request', 'mail.thread', 'mail.activity.mixin']
    _description = 'Maintenance Request Extension' # Optional: You can keep or change this description

    name = fields.Char(string="Request Title", required=True)
    description = fields.Text(string="Description of the issue")
    requestor_id = fields.Many2one(
        'res.partner', string="Requested By",
        default=lambda self: self.env.user.partner_id.id, required=True
    )
    facility_id = fields.Many2one(
        'facilities.facility', string="Facility", required=True,
        ondelete='restrict'
    )
    asset_id = fields.Many2one(
        'facilities.asset', string="Asset",
        domain="[('facility_id', '=', facility_id)]", ondelete='restrict'
    )
    category_id = fields.Many2one(
        'maintenance.request.category', string="Category",
        ondelete='set null'
    )
    date_requested = fields.Datetime(
        string="Request Date", default=fields.Datetime.now, readonly=True
    )
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string="Priority", default='1', tracking=True)

    assigned_to_id = fields.Many2one(
        'hr.employee', string="Assigned To", tracking=True,
        domain="[('work_email', '!=', False)]",
        help="The individual technician assigned to this request."
    )

    maintenance_team_id = fields.Many2one(
        'maintenance.team', string="Maintenance Team", tracking=True,
        ondelete='set null',
        required=False,  # <--- Add this line
        help="The team assigned to handle this maintenance request."
    )

    status = fields.Selection([
        ('new', 'New'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='new', tracking=True)

    date_closed = fields.Datetime(string="Close Date")
    workorder_id = fields.Many2one(
        'maintenance.workorder', string="Related Work Order", copy=False,
        help="Work Order created for this request."
    )

    # --- START OF NEW/MODIFIED CODE FOR STAGE_ID ---
    stage_id = fields.Many2one(
        'maintenance.request.stage', string='Stage',
        compute='_compute_stage_id', store=True, readonly=True,
        help="Technical field for compatibility with standard Odoo maintenance module."
    )

    @api.depends('status')
    def _compute_stage_id(self):
        """
        Maps custom 'status' values to standard 'maintenance.request.stage' records.
        These 'maintenance.stage_X' are external IDs from the core 'maintenance' module.
        'raise_if_not_found=False' prevents errors if a stage isn't found,
        allowing the field to be False.
        """
        for rec in self:
            if rec.status == 'new':
                rec.stage_id = self.env.ref('maintenance.stage_0', raise_if_not_found=False) # e.g., New/Draft
            elif rec.status == 'assigned' or rec.status == 'in_progress':
                rec.stage_id = self.env.ref('maintenance.stage_1', raise_if_not_found=False) # e.g., In Progress
            elif rec.status == 'resolved':
                rec.stage_id = self.env.ref('maintenance.stage_2', raise_if_not_found=False) # e.g., Done
            elif rec.status in ['closed', 'cancelled']:
                rec.stage_id = self.env.ref('maintenance.stage_3', raise_if_not_found=False) # e.g., Cancelled/Closed
            else:
                rec.stage_id = False # Fallback if no mapping or if stage not found
    # --- END OF NEW/MODIFIED CODE FOR STAGE_ID ---


    @api.onchange('facility_id')
    def _onchange_facility_id(self):
        if self.facility_id:
            if self.asset_id and self.asset_id.facility_id != self.facility_id:
                self.asset_id = False
        else:
            self.asset_id = False

    @api.onchange('maintenance_team_id')
    def _onchange_maintenance_team_id(self):
        if self.maintenance_team_id and self.assigned_to_id and \
                self.assigned_to_id not in self.maintenance_team_id.member_ids and \
                self.assigned_to_id != self.maintenance_team_id.leader_id:
            self.assigned_to_id = False

    def action_create_workorder(self):
        self.ensure_one()
        if self.workorder_id:
            raise UserError("A work order already exists for this request.")

        workorder_vals = {
            'request_id': self.id,
            'name': self.env['ir.sequence'].next_by_code('maintenance.workorder') or 'New',
            'asset_id': self.asset_id.id,
            'schedule_id': False,
            'technician_id': self.assigned_to_id.id if self.assigned_to_id else False,
            'maintenance_team_id': self.maintenance_team_id.id if self.maintenance_team_id else False,
            'description': self.description,
            'status': 'in_progress',
        }
        workorder = self.env['maintenance.workorder'].create(workorder_vals)
        self.workorder_id = workorder.id
        self.status = 'in_progress'
        return {
            'name': 'Work Order',
            'view_mode': 'form',
            'res_model': 'maintenance.workorder',
            'res_id': workorder.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def action_view_workorder(self):
        self.ensure_one()
        return {
            'name': 'Related Work Order',
            'view_mode': 'form',
            'res_model': 'maintenance.workorder',
            'res_id': self.workorder_id.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def action_set_assigned(self):
        self.ensure_one()
        if self.status == 'new':
            self.status = 'assigned'

    def action_set_in_progress(self):
        self.ensure_one()
        if self.status in ['new', 'assigned']:
            self.status = 'in_progress'

    def action_set_resolved(self):
        self.ensure_one()
        if self.status in ['new', 'assigned', 'in_progress']:
            self.status = 'resolved'

    def action_set_closed(self):
        self.ensure_one()
        if self.status == 'resolved':
            self.status = 'closed'
            self.date_closed = fields.Datetime.now()

    def action_set_cancelled(self):
        self.ensure_one()
        if self.status not in ['resolved', 'closed']:
            self.status = 'cancelled'

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.request') or 'New'
        return super().create(vals)

    def write(self, vals):
        if 'status' in vals and vals['status'] == 'closed' and not vals.get('date_closed'):
            vals['date_closed'] = fields.Datetime.now()
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.workorder_id:
                raise UserError(
                    "Cannot delete a request that has an associated work order. Please delete the work order first.")
        return super().unlink()


class MaintenanceRequestCategory(models.Model):
    _name = 'maintenance.request.category'
    _description = 'Maintenance Request Category'

    name = fields.Char(string="Category Name", required=True)
    description = fields.Text(string="Description")