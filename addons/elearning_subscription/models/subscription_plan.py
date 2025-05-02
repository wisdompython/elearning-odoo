from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SubscriptionPlan(models.Model):
    _name = 'elearning.subscription.plan'
    _description = 'eLearning Subscription Plan'
    _order = 'sequence, id'
    
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10, help="Determine the display order")
    price = fields.Monetary(currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    
    # Duration settings
    duration_months = fields.Integer(default=1, required=True)
    duration_days = fields.Integer(default=0)
    
    # Access limits
    free_preview_limit = fields.Integer(default=5, help="Number of videos accessible in free preview mode")
    max_courses = fields.Integer(default=0, help="Maximum number of courses. 0 = unlimited")
    max_downloads = fields.Integer(default=0, help="Maximum number of downloadable resources. 0 = unlimited")
    
    # Features
    allow_voucher = fields.Boolean(default=False, help="Allow this plan to be activated via voucher")
    allow_certification = fields.Boolean(default=False, help="Allow access to course certificates")
    allow_forum = fields.Boolean(default=False, help="Allow participation in course forums")
    
    # Courses allowed for this plan
    allowed_course_ids = fields.Many2many(
        'slide.channel',
        'elearning_subscription_plan_channel_rel',
        'plan_id', 'channel_id',
        string='Allowed Courses',
        help='Courses accessible with this subscription plan.'
    )
    
    # Product linkage for payment
    product_id = fields.Many2one('product.product', string="Related Product",
        help="Product used for payment processing")
    
    # Activity tracking
    active = fields.Boolean(default=True)
    subscription_count = fields.Integer(compute='_compute_subscription_count')
    
    @api.constrains('price')
    def _check_price(self):
        for plan in self:
            if plan.price < 0:
                raise ValidationError(_("Subscription price cannot be negative."))
    
    @api.depends()
    def _compute_subscription_count(self):
        for plan in self:
            plan.subscription_count = self.env['elearning.subscription'].search_count([
                ('plan_id', '=', plan.id)
            ])
    
    def action_view_subscriptions(self):
        """Open subscriptions for this plan"""
        self.ensure_one()
        return {
            'name': _('Subscriptions'),
            'type': 'ir.actions.act_window',
            'res_model': 'elearning.subscription',
            'view_mode': 'tree,form',
            'domain': [('plan_id', '=', self.id)],
        }