{
    'name': 'Myarra Connector',
    'version': '20.0.1.0.1',
    'category': 'Manufacturing',
    'summary': 'Read-only bridge from Odoo Manufacturing to the Myarra shop-floor tracker.',
    'description': """
Myarra Connector
================

Read-only integration between Odoo Manufacturing and the Myarra
on-premise shop-floor tracker. Extracts scheduled Manufacturing Orders
and sends them to a Myarra installation via a local API.

See the module description page for full documentation.
    """,
    'author': 'Artifexo Fabrika',
    'website': 'https://www.artifexofabrika.com',
    'license': 'OPL-1',
    'price': 99.00,
    'currency': 'USD',
    'support': 'contact@artifexofabrika.com',
    'depends': ['mrp'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/mrp_production_views.xml',
    ],
    'images': [
        'static/description/screenshot_1_dashboard.png',
        'static/description/screenshot_2_telegram.png',
        'static/description/screenshot_3_reconciliation.png',
        'static/description/screenshot_4_shift_report.png',
        'static/description/screenshot_5_odoo_sync.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
