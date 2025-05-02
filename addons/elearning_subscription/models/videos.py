from odoo import models, api, fields, _

class Channel(models.Model):
    _inherit = 'slide.channel'
    
    subscription_required = fields.Boolean(
        string='Requires Subscription', 
        help='If checked, only users with active subscriptions can access this course'
    )
    
    min_subscription_plan_id = fields.Many2one(
        'elearning.subscription.plan',
        string='Minimum Subscription Plan',
        help='Minimum subscription plan required to access this course'
    )

class Slide(models.Model):
    _inherit = 'slide.slide'
    
    def _compute_access_rights(self):
        """Extend access rights computation to include subscription checks"""
        res = super()._compute_access_rights()
        
        # Check for active subscriptions
        partner = self.env.user.partner_id
        user_subscription = self.env['elearning.subscription'].search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'active')
        ], order='end_date desc', limit=1)
        
        for slide in self:
            if slide.channel_id.subscription_required:
                # No subscription - no access
                if not user_subscription:
                    slide.can_access = False
                    continue
                    
                # Check if subscription plan meets minimum requirements
                min_plan = slide.channel_id.min_subscription_plan_id
                if min_plan and user_subscription.plan_id.id != min_plan.id:
                    slide.can_access = False
                    continue
                    
                # Check if course limit already reached
                if not user_subscription.can_access_course(slide.channel_id.id):
                    slide.can_access = False
                    continue
        
        return res
    
    @api.model
    def _record_access(self, slide_id, partner_id):
        """Track video access for subscription limits"""
        access = super()._record_access(slide_id, partner_id)
        
        # Get active subscription
        sub = self.env['elearning.subscription'].search([
            ('partner_id', '=', partner_id),
            ('state', '=', 'active')
        ], order='start_date desc', limit=1)
        
        if sub:
            # Track course access
            slide = self.browse(slide_id)
            if slide.channel_id and slide.channel_id.id not in sub.courses_accessed.ids:
                sub.write({
                    'courses_accessed': [(4, slide.channel_id.id)]
                })
            
            # Increment video consumption
            sub.write({'videos_consumed': sub.videos_consumed + 1})
            
        return access

class SlideResource(models.Model):
    _inherit = 'slide.slide.resource'
    
    def _compute_download_access(self):
        """Extend download access rights to include subscription checks"""
        res = super()._compute_download_access()
        
        partner = self.env.user.partner_id
        user_subscription = self.env['elearning.subscription'].search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'active')
        ], order='end_date desc', limit=1)
        
        for resource in self:
            if resource.slide_id.channel_id.subscription_required:
                if not user_subscription or not user_subscription.can_download_resource():
                    resource.can_download = False
                    
        return res
    
    def _download_resource(self):
        """Track resource downloads"""
        res = super()._download_resource()
        
        partner = self.env.user.partner_id
        user_subscription = self.env['elearning.subscription'].search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'active')
        ], order='end_date desc', limit=1)
        
        if user_subscription:
            user_subscription.increment_download()
            
        return res