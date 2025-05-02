from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class ElearningSubscriptionPortal(CustomerPortal):

    def _prepare_portal_layout_values(self):
        values = super(ElearningSubscriptionPortal, self)._prepare_portal_layout_values()
        subscription_count = request.env['elearning.subscription'].search_count([
            ('partner_id', '=', request.env.user.partner_id.id)
        ])
        values['subscription_count'] = subscription_count
        return values

    @http.route(['/my/subscriptions', '/my/subscriptions/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_subscriptions(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        Subscription = request.env['elearning.subscription']
        
        domain = [
            ('partner_id', '=', request.env.user.partner_id.id)
        ]
        
        # count for pager
        subscription_count = Subscription.search_count(domain)
        # pager
        pager = request.website.pager(
            url="/my/subscriptions",
            total=subscription_count,
            page=page,
            step=self._items_per_page
        )
        # content according to pager
        subscriptions = Subscription.search(
            domain,
            limit=self._items_per_page,
            offset=pager['offset']
        )
        
        values.update({
            'subscriptions': subscriptions,
            'page_name': 'subscription',
            'pager': pager,
            'default_url': '/my/subscriptions',
        })
        return request.render("elearning_subscription.portal_my_subscriptions", values)

    @http.route(['/my/subscription/<int:subscription_id>/cancel'], type='http', auth='user', website=True, csrf=True)
    def portal_subscription_cancel(self, subscription_id, **kw):
        subscription = request.env['elearning.subscription'].sudo().browse(subscription_id)
        if subscription and subscription.partner_id == request.env.user.partner_id and subscription.state in ['active', 'pending']:
            subscription.action_cancel()
            return request.redirect('/my/subscriptions')
        return request.render('elearning_subscription.portal_subscription_detail', {
            'subscription': subscription,
            'error': 'Unable to cancel this subscription.',
        }) 