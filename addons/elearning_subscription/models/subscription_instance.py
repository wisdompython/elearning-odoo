from odoo import models, fields, api, _
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class SubscriptionInstance(models.Model):
    _name = 'elearning.subscription'
    _description = 'Customer Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    
    name = fields.Char(
        readonly=True, copy=False, default=lambda self: _('New')
    )
    partner_id = fields.Many2one(
        'res.partner', required=True, ondelete='cascade', tracking=True
    )
    user_id = fields.Many2one(
        'res.users', related='partner_id.user_id', string='User'
    )
    
    # Plan information
    plan_id = fields.Many2one(
        'elearning.subscription.plan', required=True, ondelete='restrict', tracking=True
    )
    price = fields.Monetary(related='plan_id.price', readonly=True)
    currency_id = fields.Many2one('res.currency', related='plan_id.currency_id')
    
    # Dates and duration
    start_date = fields.Date(default=fields.Date.context_today, tracking=True)
    end_date = fields.Date(
        compute='_compute_end_date', store=True, tracking=True
    )
    
    # Status and tracking
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Payment'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], default='draft', required=True, tracking=True)
    
    # Usage metrics
    videos_consumed = fields.Integer(default=0)
    downloads_consumed = fields.Integer(default=0)
    courses_accessed = fields.Many2many(
        'slide.channel', string='Accessed Courses'
    )
    
    # Payment information
    payment_method_id = fields.Many2one(
        'payment.method', string='Payment Method'
    )
    invoice_id = fields.Many2one('account.move', string='Invoice')
    
    # Voucher tracking
    voucher_code = fields.Char('Applied Voucher')
    is_voucher_based = fields.Boolean(default=False)
    
    @api.depends('start_date', 'plan_id.duration_months', 'plan_id.duration_days')
    def _compute_end_date(self):
        for rec in self:
            if rec.start_date and rec.plan_id:
                months = rec.plan_id.duration_months or 0
                days = rec.plan_id.duration_days or 0
                
                # Calculate end date
                end_date = rec.start_date
                if months:
                    end_date = end_date + relativedelta(months=months)
                if days:
                    end_date = end_date + timedelta(days=days)
                    
                rec.end_date = end_date
            else:
                rec.end_date = False
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'elearning.subscription'
            ) or _('New')
        return super().create(vals)
    
    def action_activate(self):
        """Activate the subscription and enroll student in allowed courses"""
        for rec in self:
            if rec.state not in ['draft', 'pending']:
                continue
            rec.write({
                'state': 'active',
                'start_date': fields.Date.today(),
            })
            # Enroll in all courses if allowed_course_ids is empty, else only in allowed
            courses = rec.plan_id.allowed_course_ids
            if not courses:
                courses = self.env['slide.channel'].search([])
            for course in courses:
                course.sudo()._action_add_members(rec.partner_id)
            # Send welcome email
            template = self.env.ref('elearning_subscription.mail_template_subscription_activated', False)
            if template:
                template.send_mail(rec.id, force_send=True)
    
    def action_cancel(self):
        """Cancel the subscription"""
        self.write({'state': 'cancelled'})
    
    def action_expire(self):
        """Mark subscription as expired"""
        self.write({'state': 'expired'})
    
    def check_expiration(self):
        """Check if subscriptions have expired based on date"""
        today = fields.Date.today()
        expired_subs = self.search([
            ('state', '=', 'active'),
            ('end_date', '<', today)
        ])
        if expired_subs:
            expired_subs.action_expire()
            
    def check_limits(self):
        """Check subscription usage limits"""
        for rec in self.search([('state', '=', 'active')]):
            # Check free preview enforcement
            if rec.plan_id.free_preview_limit and rec.videos_consumed >= rec.plan_id.free_preview_limit:
                if rec.plan_id.price == 0:  # Only expire free plans based on consumption
                    rec.action_expire()
                    
                    # Send notification about limit reached
                    template = self.env.ref('elearning_subscription.mail_template_preview_limit_reached', False)
                    if template:
                        template.send_mail(rec.id, force_send=True)
    
    def can_access_course(self, course_id):
        """Check if subscription allows access to a specific course"""
        self.ensure_one()
        if self.state != 'active':
            return False
        # Check if the plan restricts to specific courses
        if self.plan_id.allowed_course_ids:
            if course_id not in self.plan_id.allowed_course_ids.ids:
                return False
        # Check max courses limit
        if self.plan_id.max_courses > 0:
            if len(self.courses_accessed.ids) >= self.plan_id.max_courses:
                if course_id not in self.courses_accessed.ids:
                    return False
        return True
    
    def can_download_resource(self):
        """Check if user can download a resource"""
        self.ensure_one()
        if self.state != 'active':
            return False
            
        # Check max downloads limit
        if self.plan_id.max_downloads > 0:
            if self.downloads_consumed >= self.plan_id.max_downloads:
                return False
        
        return True
    
    def increment_download(self):
        """Increment download counter"""
        self.write({'downloads_consumed': self.downloads_consumed + 1})
    
    @classmethod
    def get_active_for_partner_and_plan(cls, partner_id, plan_id):
        """Return the active subscription for this partner and plan, or None."""
        return cls.env['elearning.subscription'].search([
            ('partner_id', '=', partner_id),
            ('plan_id', '=', plan_id),
            ('state', '=', 'active')
        ], limit=1)