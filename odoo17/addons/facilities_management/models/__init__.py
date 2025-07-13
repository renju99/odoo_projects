# models/__init__.py
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# Standard way to import models in Odoo modules
# Ensure all your model files are listed here in a logical dependency order.
# facility.py should generally be imported early if other models depend on it.
from . import facility
from . import asset_category
from . import asset
from . import asset_maintenance_schedule
from . import maintenance_workorder
from . import asset_depreciation
from . import predictive_maintenance
from . import maintenance_workorder_assignment
from . import hr_employee
from . import maintenance_workorder_part_line
from . import product

# The pre_init_hook can remain if its logic is still desired
def pre_init_hook(cr):
    """Ensure clean slate"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("Running pre_init_hook for facilities_management...")
    try:
        # Check if the tables/models exist before trying to delete from ir.model
        # This prevents errors if running for the first time or if models aren't registered yet
        cr.execute("""
            DELETE FROM ir_model WHERE model = 'facilities.facility';
            DELETE FROM ir_model_data WHERE model = 'ir.model' AND name LIKE 'model_facilities%';
        """)
        _logger.info("Cleaned up old facilities.facility model entries (if any).")
    except Exception as e:
        _logger.warning(f"Failed to run pre_init_hook cleanup: {e}")