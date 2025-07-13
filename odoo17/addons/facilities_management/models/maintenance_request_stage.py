# /home/ranjith/odoo_projects/odoo17/addons/facilities_management/models/maintenance_request_stage.py

from odoo import models, fields, api

class MaintenanceRequestStage(models.Model):
    _name = 'maintenance.request.stage'
    _description = 'Maintenance Request Stage'
    _order = 'sequence, name'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    fold = fields.Boolean(string='Folded in Kanban',
                          help='This stage is folded in the Kanban view when there are no records in it.')
    # ADD THIS FIELD: 'done'
    done = fields.Boolean(string='Done Stage',
                          help="If checked, requests in this stage are considered done/completed.")
    # You might also want to add a 'cancelled' or 'closed' boolean field if your stages include those
    # cancelled = fields.Boolean(string='Cancelled Stage', help="If checked, requests in this stage are considered cancelled.")
    # closed = fields.Boolean(string='Closed Stage', help="If checked, requests in this stage are considered closed.")