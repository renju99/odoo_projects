# -*- coding: utf-8 -*-

import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# Standard way to import models in Odoo modules
# Ensure all your model files are listed here in a logical dependency order.

# 1. Base/Configuration/Lookup Models (Least dependencies within module)
from . import hr_employee
from . import product
from . import maintenance_team
from . import maintenance_request_stage
from . import maintenance_workorder_type

# REMOVED: from . import maintenance_job_plan_task (as it's defined in maintenance_job_plan.py)
from . import maintenance_job_plan      # <--- This import is correct and will load both classes

# 2. Core Infrastructure & Assets (Hierarchical, depends on basic Odoo models)
from . import building
from . import floor
from . import room
from . import facility
from . import asset_category
from . import asset

# 3. Asset Performance (depends on asset)
from . import asset_performance

# 4. Transactional Models (Depend on many of the above)
from . import maintenance_request
from . import maintenance_workorder
from . import maintenance_workorder_assignment
from . import maintenance_workorder_part_line
from . import maintenance_workorder_task
from . import maintenance_job_plan_section
from . import maintenance_job_plan_task
from . import maintenance_job_plan
from . import maintenance_workorder_section
from . import stock_picking

# 5. Scheduled/Predictive Maintenance (Often depend on assets and work orders)
from . import asset_maintenance_schedule
from . import predictive_maintenance
from . import asset_depreciation

# NEW IMPORTS FOR SLA AND RESOURCE UTILIZATION
from . import hr_employee_extension
from . import workorder_sla
from . import resource_utilization
from . import sla_analytics
from . import workorder_sla_integration


# The pre_init_hook can remain if its logic is still desired
def pre_init_hook(cr):
    """Ensure clean slate"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("Running pre_init_hook for facilities_management...")
    try:
        cr.execute("""
            DELETE FROM ir_model WHERE model = 'facilities.facility';
            DELETE FROM ir_model_data WHERE model = 'ir.model' AND name LIKE 'model_facilities%';
        """)
        _logger.info("Cleaned up old facilities.facility model entries (if any).")
    except Exception as e:
        _logger.warning(f"Failed to run pre_init_hook cleanup: {e}")