from odoo import http
from odoo.http import request
import logging
import hmac
import hashlib
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentPaystackController(http.Controller):
    @http.route(
        '/payment/paystack/checkout',
        type='http',
        auth='public',
        website=True
    )
    def paystack_checkout(self, **kwargs):
        """Redirect user to Paystack payment page."""
        try:
            tx_sudo = request.env['payment.transaction'].sudo().browse(
                int(kwargs.get('transaction_id'))
            )
            provider = tx_sudo.provider_id
            paystack_values = provider.paystack_form_generate_values(
                tx_sudo._get_specific_rendering_values('paystack')
            )
            _logger.info(
                "Initiating Paystack payment for transaction %s",
                tx_sudo.reference
            )
            return request.render('payment_paystack.paystack_redirect', {
                'paystack_values': paystack_values,
                'paystack_public_key': provider.paystack_public_key,
            })
        except Exception as e:
            _logger.exception(
                "Error during Paystack checkout for transaction %s: %s",
                kwargs.get('transaction_id'),
                str(e)
            )
            return request.render(
                'payment_paystack.paystack_error',
                {'error': 'An error occurred during checkout.'}
            )

    @http.route(
        '/payment/paystack/return',
        type='http',
        auth='public',
        website=True
    )
    def paystack_return(self, **kwargs):
        """Handle Paystack's redirect after payment."""
        reference = kwargs.get('reference')
        if not reference:
            _logger.error("Missing reference in Paystack return URL")
            return request.render(
                'payment_paystack.paystack_error',
                {'error': 'Missing payment reference.'}
            )

        try:
            tx = request.env['payment.transaction'].sudo().search(
                [('reference', '=', reference)], limit=1
            )
            if not tx:
                _logger.error(
                    "Transaction not found for reference %s", reference
                )
                return request.render(
                    'payment_paystack.paystack_error',
                    {'error': 'Transaction not found.'}
                )

            # Verify payment with Paystack
            provider = tx.provider_id
            _logger.info(
                "Verifying Paystack payment for transaction %s", reference
            )
            result = provider._paystack_make_request(
                f"transaction/verify/{reference}", method='GET'
            )
            
            if not result.get('status'):
                _logger.error(
                    "Paystack verification failed for transaction %s: %s",
                    reference,
                    result.get('message', 'Unknown error')
                )
                tx._set_canceled()
                return request.render(
                    'payment_paystack.paystack_error',
                    {'error': 'Payment verification failed.'}
                )

            if result['data']['status'] == 'success':
                _logger.info(
                    "Paystack payment verified successfully for transaction %s",
                    reference
                )
                tx._set_done()
                return request.render(
                    'payment_paystack.paystack_success',
                    {'tx': tx}
                )
            else:
                _logger.warning(
                    "Paystack payment not successful for transaction %s: %s",
                    reference,
                    result['data']['status']
                )
                tx._set_canceled()
                return request.render(
                    'payment_paystack.paystack_error',
                    {'error': 'Payment was not successful.'}
                )

        except Exception as e:
            _logger.exception(
                "Error during Paystack return for reference %s: %s",
                reference,
                str(e)
            )
            return request.render(
                'payment_paystack.paystack_error',
                {'error': 'An error occurred while processing your payment.'}
            )

    @http.route('/payment/paystack/webhook', type='json', auth='public')
    def paystack_webhook(self, **post):
        """Handle Paystack webhook notifications."""
        _logger.info("Paystack webhook received: %s", post)
        
        try:
            # Verify webhook signature
            provider = request.env['payment.provider'].sudo().search(
                [('code', '=', 'paystack')], limit=1
            )
            if not provider:
                _logger.error("Paystack provider not found in webhook")
                return {'status': 'error', 'message': 'Provider not found'}

            # Get the signature from the request headers
            signature = request.httprequest.headers.get('X-Paystack-Signature')
            if not signature:
                _logger.error("Missing Paystack signature in webhook")
                return {'status': 'error', 'message': 'Missing signature'}

            # Verify the signature
            expected_signature = hmac.new(
                provider.paystack_secret_key.encode('utf-8'),
                request.httprequest.data,
                hashlib.sha512
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                _logger.error("Invalid Paystack signature in webhook")
                return {'status': 'error', 'message': 'Invalid signature'}

            # Process the webhook data
            event = post.get('event')
            data = post.get('data', {})

            if event == 'charge.success':
                reference = data.get('reference')
                if not reference:
                    _logger.error("Missing reference in webhook data")
                    return {'status': 'error', 'message': 'Missing reference'}

                tx = request.env['payment.transaction'].sudo().search(
                    [('reference', '=', reference)], limit=1
                )
                if not tx:
                    _logger.error(
                        "Transaction not found for reference %s in webhook",
                        reference
                    )
                    return {'status': 'error', 'message': 'Transaction not found'}

                _logger.info(
                    "Webhook: Setting transaction %s to done", reference
                )
                tx._set_done()
                return {'status': 'ok'}

            else:
                _logger.info(
                    "Received unhandled Paystack webhook event: %s", event
                )
                return {'status': 'ok'}

        except Exception as e:
            _logger.exception(
                "Error processing Paystack webhook: %s", str(e)
            )
            return {'status': 'error', 'message': str(e)}

