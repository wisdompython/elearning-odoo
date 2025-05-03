# -*- coding: utf-8 -*-
{
    'name': "Paystack Payment Acquirer",
    'summary': "Payment Acquirer: Paystack Implementation",
    'description': """
Paystack Payment Acquirer
========================
Paystack payment gateway integration for Odoo.

Features:
---------
- Accept payments via Paystack
- Support for multiple currencies
- Secure payment processing
- Webhook support for payment notifications
    """,
    'author': "Your Company",
    'website': "https://www.yourcompany.com",
    'category': 'Accounting/Payment',
    'version': '1.0',
    'depends': [
        'payment',
        'website',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_provider_views.xml',
        'views/payment_paystack_templates.xml',
        'data/payment_provider_data.xml',
        'data/payment_method.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

