{
    'name': 'Facilities Management',
    'version': '1.0',
    'depends': ['base', 'mail' , 'hr'],
    'data': [
        'data/sequences.xml',
        'security/facility_management_security.xml',
        'security/ir.model.csv',
        'security/ir.model.access.csv',

        # View files only (no Python files here)
        'views/facility_views.xml',
        'views/asset_category_views.xml',
        'views/facility_asset_views.xml',
        'views/asset_maintenance_schedule_views.xml',
        'views/asset_maintenance_calendar_views.xml',
        'views/maintenance_workorder_views.xml',
        'views/maintenance_report_views.xml',
        'views/asset_dashboard_views.xml',
        'views/asset_maintenance_scheduled_actions.xml',
        'views/facility_asset_menus.xml',
        'views/facility_asset_search.xml',
        'views/email_templates.xml'
    ],
    'installable': True,
    'application': True,
}

# New test is done