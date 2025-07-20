{
    'name': 'Facilities Management',
    'version': '2.1.0',
    'category': 'Operations/Maintenance',
    'summary': 'Comprehensive Facilities and Asset Management with SLA and Resource Utilization',
    'depends': [
        'base',
        'mail',
        'hr',
        'web',
        'maintenance',
        'sale_management',
        'stock',
        'product',
        'account',
    ],
    'data': [
        # Security and sequences first
        'data/sequences.xml',
        'data/predictive_parameters.xml',
        'data/maintenance_cron.xml',
        'data/email_templates.xml',
        'security/facility_management_security.xml',
        'security/ir.model.access.csv',

        # Core entity views in dependency order
        'views/room_views.xml',
        'views/floor_views.xml',
        'views/building_views.xml',
        'views/facility_views.xml',

        # Other core views
        'views/asset_category_views.xml',
        'views/facility_asset_views.xml',

        # Maintenance features
        'views/asset_maintenance_schedule_views.xml',
        'views/asset_maintenance_calendar_views.xml',
        'views/maintenance_workorder_views.xml',
        'views/maintenance_workorder_kanban.xml',
        'views/asset_maintenance_scheduled_actions.xml',
        'views/maintenance_workorder_part_line_views.xml',
        'views/product_views.xml',
        'views/maintenance_job_plan_views.xml',
        'views/maintenance_team_views.xml',
        'views/sla_views.xml',
        'views/asset_performance_views.xml',
        'views/asset_calendar_views.xml',
        'views/assign_technician_wizard_view.xml',

        # Reporting and Dashboards
        'views/maintenance_report_views.xml',
        'reports/maintenance_report.xml',
        'views/asset_dashboard_views.xml',

        # UI Menus
            'views/facility_asset_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'facilities_management/static/src/css/facilities.css',
            'facilities_management/static/src/js/dashboard_widgets.js',
        ],
        'web.assets_frontend': [
            'facilities_management/static/src/css/portal.css',
        ],
    },
    'external_dependencies': {
        'python': ['qrcode', 'Pillow'],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}