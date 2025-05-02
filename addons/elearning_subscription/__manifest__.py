{
    "name": "eLearning Subscription Plans",
    "version": "1.0.0",
    "summary": "Three-tier subscription: Free Preview, Standard, Scholar (voucher based)",
    "category": "eLearning",
    "author": "Your Company",
    "website": "https://yourcompany.example.com",
    "depends": [
        "website_slides",    # Odoo eLearning module (correct name)
        "sale",              # Core sale module for orders/invoices
        "payment",           # Payment processing
        "website_sale",      # Website sale integration
        "loyalty"             # Coupon/voucher system
    ],
    "data": [
        # Security
        "security/security.xml",
        "security/ir.model.access.csv",
        
        # Data
        "data/subscription_plan_data.xml",
        "data/cron_subscription_checks.xml",
        
        # Views
        "views/subscription_plan_views.xml",
        "views/subscription_instance_views.xml",
        "views/portal_templates.xml",
        "views/payment_templates.xml",
        
        # Menus
        "views/menu_views.xml",
    ],
    # "assets": {
    #     "web.assets_frontend": [
    #         "elearning_subscription/static/src/js/subscription_portal.js",
    #         "elearning_subscription/static/src/css/subscription_portal.css",
    #     ],
    # },
    "installable": True,
    "application": False,
    "license": "LGPL-3"
}