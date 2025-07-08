# __manifest__.py
{
    'name': 'Facilities Management',
    'version': '2.0.0',
    'depends': [
        'base',
        'mail',
        'hr',
        'web',  # <--- ADD THIS LINE
    ],
    'data': [
        # Security and sequences first
        'data/sequences.xml',
        'data/predictive_parameters.xml',
        'data/maintenance_cron.xml',
        'security/facility_management_security.xml',
        'security/ir.model.csv',
        'security/ir.model.access.csv',

        # Core views
        'views/facility_views.xml',
        'views/asset_category_views.xml',
        'views/facility_asset_views.xml',
        # 'views/asset_iot_views.xml', # This should already be removed

        # Maintenance features
        'views/asset_maintenance_schedule_views.xml',
        'views/asset_maintenance_calendar_views.xml',
        'views/maintenance_workorder_views.xml',
        'views/asset_maintenance_scheduled_actions.xml',
        'views/predictive_algorithm_views.xml',

        # Reporting
        'views/maintenance_report_views.xml',
        'reports/maintenance_report.xml',
        'views/asset_dashboard_views.xml',
        'views/asset_dashboard_community.xml',

        # UI
        'views/facility_asset_menus.xml',
        'views/facility_asset_search.xml',
        # 'views/iot_asset_dashboard.xml', # This should also be removed if it existed
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'description': """
        Facilities Management Module for Odoo
        =====================================
        This module provides comprehensive management for facilities and assets,
        including asset tracking, maintenance scheduling, and predictive analysis.
    """,
}