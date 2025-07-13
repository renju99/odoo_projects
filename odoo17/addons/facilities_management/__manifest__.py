# __manifest__.py
{
    'name': 'Facilities Management',
    'version': '2.0.0',
    'depends': [
        'base',
        'mail',
        'hr',
        'web',
        'maintenance',
        'sale_management',
        'stock',
        'product',
        'account',         # Keep this for Monetary fields & Currency
        # 'web_enterprise',  # <--- REMOVE THIS LINE
    ],
    'data': [
        # Security and sequences first
        'data/sequences.xml',
        'data/predictive_parameters.xml',
        'data/maintenance_cron.xml',
        'data/email_templates.xml',
        'security/facility_management_security.xml',
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
        'views/maintenance_workorder_part_line_views.xml',
        'views/product_views.xml',

        # Reporting
        'views/maintenance_report_views.xml',
        'reports/maintenance_report.xml',
        # 'views/asset_dashboard_views.xml', # This might be the Enterprise dashboard, will disable for now
        'views/asset_dashboard_community.xml', # <--- Keep this for Community dashboard

        # UI
        'views/facility_asset_menus.xml',
        # ... (rest of your data files)
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}