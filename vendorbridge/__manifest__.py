{
    'name': 'VendorBridge',
    'version': '17.0.1.0.0',
    'category': 'Purchases',
    'summary': 'Procurement & Vendor Management ERP',
    'description': 'Centralized procurement platform for vendor management, RFQs, quotations, approvals, purchase orders, and invoices.',
    'author': 'VendorBridge Team',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'product',
        'auth_signup',
        'portal',
        'web',
    ],
    'data': [
        # Security
        'security/vendorbridge_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/sequences.xml',
        # Reports (must load before mail_templates — invoice template references report action)
        'report/invoice_report.xml',
        'report/po_report.xml',
        # Mail Templates
        'data/mail_templates.xml',
        # Views
        'views/menu.xml',
        'views/dashboard_views.xml',
        'views/vendor_views.xml',
        'views/rfq_views.xml',
        'views/quotation_views.xml',
        'views/approval_workflow_views.xml',
        'views/purchase_order_views.xml',
        'views/invoice_views.xml',
        'views/activity_log_views.xml',
        'views/report_analytics_views.xml',
        'views/settings_views.xml',
        'views/portal_templates.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'vendorbridge/static/src/css/dashboard.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
