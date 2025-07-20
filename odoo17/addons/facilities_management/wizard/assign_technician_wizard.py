from odoo import models, fields

class AssignTechnicianWizard(models.TransientModel):
    _name = 'assign.technician.wizard'
    _description = 'Assign Technician Wizard'

    technician_id = fields.Many2one('hr.employee', string="Technician", required=True)
    workorder_id = fields.Many2one('maintenance.workorder', string="Work Order", required=True)

    def action_assign(self):
        self.workorder_id.technician_id = self.technician_id.id