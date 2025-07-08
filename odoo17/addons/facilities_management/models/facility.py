# models/facility.py
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class Facility(models.Model):
    _name = 'facilities.facility'
    _description = 'Facility Management'
    # _auto = True # _auto is True by default for new models, no need to explicitly set it unless you want to set it to False

    name = fields.Char(required=True)
    code = fields.Char(string='Facility Code', required=True, copy=False, readonly=True, default='New')
    manager_id = fields.Many2one('hr.employee', string='Facility Manager', tracking=True)
    active = fields.Boolean(default=True)

    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('facilities.facility') or 'New'
        result = super(Facility, self).create(vals)
        return result

    # REMOVE THE ENTIRE _register_hook METHOD
    # @api.model
    # def _register_hook(self):
    #     """Nuclear option for registration"""
    #     super()._register_hook()
    #     if not hasattr(self.pool, self._name):
    #         _logger.warning("FORCING model registration for %s", self._name)
    #         self.pool[self._name] = self
    #         self.env.registry[self._name] = self
    #         # Force field registration
    #         for fname, field in self._fields.items():
    #             field.model_name = self._name