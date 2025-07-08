from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Ensure all work orders have valid technicians
    env['maintenance.workorder'].search([]).write({
        'technician_id': env.ref('base.user_admin').employee_id.id
    })