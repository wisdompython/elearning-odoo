from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, ValidationError
import werkzeug

class ElearningSubscriptionPortal(CustomerPortal):
    @http.route(['/my/subscriptions'], type='http', auth='user', website=True)
    def portal_subscriptions(self):
        """Display customer subscriptions"""
        partner = request.env.user.partner_id
        subscriptions = request.env['elearning.subscription'].search([
            ('partner_id', '=', partner.id)
        ])
        
        # Get available plans for purchase
        plans = request.env['elearning.subscription.plan'].search([
            ('active', '=', True),
            ('price', '>', 0),
        ])
        
        values = {
            'subscriptions': subscriptions,
            'plans': plans,
            'page_name': 'subscriptions',
        }
        
        return request.render('elearning_subscription.portal_subscriptions', values)
        
    @http.route(['/my/subscription/<int:subscription_id>'], type='http', auth='user', website=True)
    def portal_subscription_detail(self, subscription_id=None, **kw):
        """Display subscription details"""
        subscription = request.env['elearning.subscription'].browse(subscription_id)
        
        # Security check
        if not subscription.exists() or subscription.partner_id != request.env.user.partner_id:
            return request.redirect('/my/subscriptions')
            
        values = {
            'subscription': subscription,
            'page_name': 'subscription_detail',
        }
        
        return request.render('elearning_subscription.portal_subscription_detail', values)
        
    @http.route(['/subscription/purchase/<int:plan_id>'], type='http', auth='user', website=True)
    def purchase_subscription(self, plan_id=None, **kw):
        """Create a subscription and initiate payment"""
        plan = request.env['elearning.subscription.plan'].browse(plan_id)
        if not plan.exists() or not plan.active:
            return request.redirect('/my/subscriptions')
        partner_id = request.env.user.partner_id.id
        existing = request.env['elearning.subscription'].get_active_for_partner_and_plan(partner_id, plan.id)
        if existing:
            return request.redirect(f'/my/subscription/{existing.id}')
        # Create draft subscription
        subscription = request.env['elearning.subscription'].create({
            'partner_id': partner_id,
            'plan_id': plan.id,
            'state': 'pending',
        })
        # Create payment link
        payment_link = request.env['payment.link.wizard'].create({
            'amount': plan.price,
            'currency_id': plan.currency_id.id,
            'partner_id': partner_id,
            'subscription_id': subscription.id,
            'description': f"Subscription to {plan.name}",
            'res_id': subscription.id,
            'res_model': 'elearning.subscription'
        })
        return request.redirect(payment_link.link)

    @http.route(['/subscription/purchase/free/<int:plan_id>'], type='http', auth='user', website=True)
    def free_subscription(self, plan_id=None, **kw):
        """Create and activate a free subscription for the user."""
        plan = request.env['elearning.subscription.plan'].browse(plan_id)
        if not plan.exists() or not plan.active or plan.price > 0:
            return request.redirect('/my/subscriptions')
        partner_id = request.env.user.partner_id.id
        existing = request.env['elearning.subscription'].get_active_for_partner_and_plan(partner_id, plan.id)
        if existing:
            return request.redirect(f'/my/subscription/{existing.id}')
        # Create and activate the subscription
        subscription = request.env['elearning.subscription'].create({
            'partner_id': partner_id,
            'plan_id': plan.id,
            'state': 'active',
            'start_date': fields.Date.today(),
        })
        return request.redirect(f'/my/subscription/{subscription.id}')
    
    @http.route(['/apply-voucher'], type='http', auth='user', methods=['POST'], website=True)
    def apply_voucher(self, code=None, **post):
        """Apply voucher code to get a subscription"""
        if not code:
            return request.redirect('/my/subscriptions')
            
        # Validate voucher/coupon code
        program = request.env['loyalty.program'].sudo().search([
            ('code', '=', code), 
            ('state', '=', 'running')
        ], limit=1)
        
        if not program:
            return request.render('elearning_subscription.voucher_error', {
                'message': _('Invalid or expired voucher code.'),
            })
            
        # Find a plan that allows vouchers
        plan = request.env['elearning.subscription.plan'].search([
            ('allow_voucher', '=', True),
            ('active', '=', True),
        ], limit=1)
        
        if not plan:
            return request.render('elearning_subscription.voucher_error', {
                'message': _('No subscription plan accepts vouchers.'),
            })
            
        # Create and activate subscription
        subscription = request.env['elearning.subscription'].create({
            'partner_id': request.env.user.partner_id.id,
            'plan_id': plan.id,
            'voucher_code': code,
            'is_voucher_based': True,
        })
        
        subscription.action_activate()
        
        # Show success message
        return request.render('elearning_subscription.voucher_success', {
            'subscription': subscription,
        })