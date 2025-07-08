# models/__post_init__.py
from odoo import api, SUPERUSER_ID, fields


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Maintain existing technician assignment
    env['maintenance.workorder'].search([]).write({
        'technician_id': env.ref('base.user_admin').employee_id.id
    })

    # 2. Predictive Maintenance Defaults
    _setup_predictive_parameters(env)

    # 4. Migrate old schedules to new format
    _migrate_legacy_schedules(env)


def _setup_predictive_parameters(env):
    """Configure default predictive maintenance thresholds"""
    params = env['ir.config_parameter']

    params.set_param('facilities.predictive.usage_threshold', '500')  # Hours/miles
    params.set_param('facilities.predictive.time_threshold', '30')  # Days
    # Removed: params.set_param('facilities.predictive.iot_variance', '0.15')  # 15% tolerance

    # Create default algorithm mapping
    env['predictive.algorithm'].create({
        'name': 'Default Linear Model',
        'model_type': 'linear',
        'asset_type_ids': [(4, env.ref('facilities_management.model_facilities_asset').id)]
    })


def _migrate_legacy_schedules(env):
    """Convert old schedules to predictive format"""
    legacy_schedules = env['asset.maintenance.schedule'].search([
        ('predictive_algorithm', '=', False)
    ])

    legacy_schedules.write({
        'predictive_algorithm': 'time',
        'time_threshold': 30  # Default 30-day intervals
    })