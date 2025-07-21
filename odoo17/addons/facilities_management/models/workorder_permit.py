from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MaintenanceWorkorderPermit(models.Model):
    _name = 'maintenance.workorder.permit'
    _description = 'Work Order Permit'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Permit Name", required=True, tracking=True)
    permit_type = fields.Selection([
        ('electrical', 'Electrical'),
        ('mechanical', 'Mechanical'),
        ('hotwork', 'Hot Work'),
        ('confined', 'Confined Space'),
        ('general', 'General'),
    ], string="Permit Type", required=True, tracking=True)
    workorder_id = fields.Many2one('maintenance.workorder', string="Work Order", required=True, ondelete='cascade', tracking=True)
    issued_date = fields.Date(string="Issued Date", tracking=True)
    expiry_date = fields.Date(string="Expiry Date", tracking=True)
    status = fields.Selection([
        ('requested', 'Requested'),
        ('pending_manager_approval', 'Pending Manager Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ], string="Status", default='requested', required=True, tracking=True)
    notes = fields.Text(string="Notes")
    requested_by_id = fields.Many2one('res.users', string="Requested By", default=lambda self: self.env.user, tracking=True)
    approved_by_id = fields.Many2one('res.users', string="Approved By", tracking=True)
    rejected_reason = fields.Text(string="Rejection Reason", tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    facility_manager_id = fields.Many2one(
        'res.users',
        string="Facility Manager",
        compute='_compute_facility_manager',
        store=False,
    )

    @api.depends('workorder_id')
    def _compute_facility_manager(self):
        for permit in self:
            manager = False
            if permit.workorder_id and permit.workorder_id.asset_id and permit.workorder_id.asset_id.facility_id:
                facility = permit.workorder_id.asset_id.facility_id
                manager = facility.manager_id
                if hasattr(manager, 'user_id') and manager.user_id:
                    permit.facility_manager_id = manager.user_id
                elif manager and manager._name == 'res.users':
                    permit.facility_manager_id = manager
                else:
                    permit.facility_manager_id = False
            else:
                permit.facility_manager_id = False

    def action_submit_for_approval(self):
        for permit in self:
            if permit.status != 'requested':
                raise UserError(_("Permit is not in 'Requested' stage!"))
            manager_user = permit.facility_manager_id
            if not manager_user:
                raise UserError(_("No facility manager found for this permit's facility."))
            permit.status = 'pending_manager_approval'
            # Create scheduled activity for the manager
            activity_type = self.env.ref('mail.mail_activity_data_todo')
            model_id = self.env['ir.model']._get_id('maintenance.workorder.permit')
            self.env['mail.activity'].create({
                'activity_type_id': activity_type.id,
                'res_id': permit.id,
                'res_model_id': model_id,
                'user_id': manager_user.id,
                'summary': _("Permit Approval Required"),
                'note': _("Please approve permit '%s' for work order '%s'.") % (permit.name, permit.workorder_id.name),
                'date_deadline': fields.Date.today(),
            })
            permit.message_post(body=_("Approval request sent to Facility Manager: %s" % manager_user.name),
                                partner_ids=[manager_user.partner_id.id])

    def action_approve(self):
        for permit in self:
            manager_user = permit.facility_manager_id
            if permit.status != 'pending_manager_approval':
                raise UserError(_("Permit is not awaiting manager approval."))
            if manager_user and self.env.user == manager_user:
                permit.status = 'approved'
                permit.approved_by_id = self.env.user.id
                permit.issued_date = fields.Date.today()  # Set issued date to approval date
                permit.message_post(body=_("Permit approved by Facility Manager."))
            else:
                raise UserError(_("Only the facility manager of this facility can approve this permit."))

    def action_reject(self):
        for permit in self:
            manager_user = permit.facility_manager_id
            if permit.status != 'pending_manager_approval':
                raise UserError(_("Permit is not awaiting manager approval."))
            if manager_user and self.env.user == manager_user:
                # Require rejection reason
                if not permit.rejected_reason:
                    raise UserError(_("Please provide a rejection reason before rejecting the permit."))
                permit.status = 'rejected'
                permit.message_post(body=_("Permit rejected by Facility Manager. Reason: %s" % permit.rejected_reason))
            else:
                raise UserError(_("Only the facility manager of this facility can reject this permit."))