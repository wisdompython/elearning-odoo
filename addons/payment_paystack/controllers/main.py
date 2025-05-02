# # -*- coding: utf-8 -*-
# # from odoo import http




# import logging
# import pprint

# from odoo import http
# from odoo.exceptions import ValidationError
# from odoo.http import request

# class PaymentPaystack(http.Controller):
#     _return_url = '/payment/paystack/return'
#     _auth_return_url = '/payment/paystack/auth_return'
#     _webhook_url = '/payment/paystack/webhook'


#     @http.route(_return_url, methods=['GET'], auth='public')
#     def index(self, **kw):
#         return "Hello, world"

from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class PaymentPaystackController(http.Controller):
    @http.route('/payment/paystack/checkout', type='http', auth='public', website=True)
    def paystack_checkout(self, **kwargs):
        """Redirect user to Paystack payment page."""
        tx_sudo = request.env['payment.transaction'].sudo().browse(int(kwargs.get('transaction_id')))
        provider = tx_sudo.provider_id
        paystack_values = provider.paystack_form_generate_values(tx_sudo._get_specific_rendering_values('paystack'))
        # Render a template or redirect to Paystack's payment page using JS
        return request.render('payment_paystack.paystack_redirect', {
            'paystack_values': paystack_values,
            'paystack_public_key': provider.paystack_public_key,
        })

    @http.route('/payment/paystack/return', type='http', auth='public', website=True)
    def paystack_return(self, **kwargs):
        """Handle Paystack's redirect after payment."""
        reference = kwargs.get('reference')
        tx = request.env['payment.transaction'].sudo().search([('reference', '=', reference)], limit=1)
        if not tx:
            return request.render('payment_paystack.paystack_error', {'error': 'Transaction not found.'})

        # Verify payment with Paystack
        provider = tx.provider_id
        result = provider._paystack_make_request(f"transaction/verify/{reference}", method='GET')
        if result.get('status') and result['data']['status'] == 'success':
            tx._set_done()
            return request.render('payment_paystack.paystack_success', {'tx': tx})
        else:
            tx._set_canceled()
            return request.render('payment_paystack.paystack_error', {'error': 'Payment failed.'})

    @http.route('/payment/paystack/webhook', type='json', auth='public')
    def paystack_webhook(self, **post):
        """Handle Paystack webhook notifications."""
        # Implement webhook signature verification and transaction update here
        _logger.info("Paystack webhook received: %s", post)
        # You would typically verify the event and update the transaction
        return {'status': 'ok'}
