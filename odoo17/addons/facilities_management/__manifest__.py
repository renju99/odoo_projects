# __manifest__.py
{
    'name': 'Facilities Management',
    'version': '2.0.0',
    'depends': [
        'base',
        'mail',
        'hr',
        'web',
        'maintenance', # This dependency is important for the maintenance menu items
        'sale_management',
        'stock',
        'product',
        'account',
    ],
    'data': [
        # Security and sequences first (always recommended to load early)
        'data/sequences.xml',
        'data/predictive_parameters.xml',
        'data/maintenance_cron.xml',
        'data/email_templates.xml',
        'security/facility_management_security.xml',
        'security/ir.model.access.csv', # CRITICAL: Ensure access rules for Building, Floor, Room are added here!

        # Core entity views in dependency order (Rooms -> Floors -> Buildings -> Facilities)
        # Load actions and views for Rooms first, as they are the 'leaf' entities
        'views/room_views.xml',     # MOVED UP: Defines action_facilities_room
        'views/floor_views.xml',    # MOVED UP: Defines action_facilities_floor, references action_facilities_room
        'views/building_views.xml', # MOVED UP: Defines action_facilities_building, references action_facilities_floor
        'views/facility_views.xml', # This now correctly references action_facilities_building

        # Other core views
        'views/asset_category_views.xml',
        'views/facility_asset_views.xml',

        # Maintenance features
        'views/asset_maintenance_schedule_views.xml',
        'views/asset_maintenance_calendar_views.xml',
        'views/maintenance_workorder_views.xml',
        'views/asset_maintenance_scheduled_actions.xml',
        'views/maintenance_workorder_part_line_views.xml',
        'views/product_views.xml',
        'views/maintenance_job_plan_views.xml', # ADD THIS LINE HERE

        # Reporting
        'views/maintenance_report_views.xml',
        'reports/maintenance_report.xml',
        'views/asset_dashboard_views.xml',

        # UI Menus (typically loaded last as they reference actions and models defined in previous files)
        'views/facility_asset_menus.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}