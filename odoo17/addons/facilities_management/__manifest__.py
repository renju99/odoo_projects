# __manifest__.py
{
    'name': 'Facilities Management',
    'version': '2.0.0',
    'depends': [
        'base',
        'mail',
        'hr',
        'web',
    ],
    'data': [
        # Security and sequences first
        'data/sequences.xml',
        'data/maintenance_cron.xml',
        'security/facility_management_security.xml',
        'security/ir.model.csv',
        'security/ir.model.access.csv',

        # Core views
        'views/facility_views.xml',
        'views/asset_category_views.xml',
        'views/facility_asset_views.xml',

        # Maintenance features
        'views/asset_maintenance_schedule_views.xml',
        'views/asset_maintenance_calendar_views.xml',
        'views/maintenance_workorder_views.xml',
        'views/asset_maintenance_scheduled_actions.xml',
        'views/predictive_algorithm_views.xml',
        # If you were to create a standalone view for assignment, you'd add it here:
        # 'views/maintenance_workorder_assignment_views.xml',

        # Reporting
        'views/maintenance_report_views.xml',
        'reports/maintenance_report.xml',
        'views/asset_dashboard_views.xml',
        'views/asset_dashboard_community.xml',

        # UI
        'views/facility_asset_menus.xml',
        'views/facility_asset_search.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}