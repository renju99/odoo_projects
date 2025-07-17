# Python
from odoo import models, api

class MaintenanceReport(models.AbstractModel):
    _name = 'report.facilities_management.report_asset_maintenance_template'

    @api.model
    def _get_report_values(self, docids, data=None):
        assets = self.env['facilities.asset'].browse(docids)
        return {
            'docs': assets,
        }