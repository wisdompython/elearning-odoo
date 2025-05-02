from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare
import logging
from werkzeug import urls

_logger = logging.getLogger(__name__)

class PaymentTransactionPaystack(models.Model):
    _inherit = "payment.transaction"

    paystack_reference = fields.Char('Paystack Reference', readonly=True)
    paystack_payment_url = fields.Char('Paystack Payment URL', readonly=True)

    @api.model
    def _paystack_form_get_tx_from_data(self, data):
        reference = data.get('reference')
        if not reference:
            _logger.error('Paystack: missing reference in data')
            raise ValidationError(_('Missing payment reference from Paystack.'))
        tx = self.search([('reference', '=', reference)], limit=1)
        if not tx:
            _logger.error('Paystack: no transaction found for reference %s', reference)
            raise ValidationError(_('No transaction found for reference %s') % reference)
        return tx

    def _paystack_form_get_invalid_parameters(self, data):
        invalid = []
        # Validate amount (Paystack returns amount in kobo)
        amount = data.get('amount', 0) / 100.0
        if float_compare(amount, self.amount, precision_digits=2) != 0:
            invalid.append(('amount', amount, self.amount))
        return invalid

    def _paystack_form_validate(self, data):
        status = data.get('status')
        vals = {
            'provider_reference': data.get('id'),
            'paystack_reference': data.get('reference'),
            'date': fields.Datetime.now(),
        }
        self.write(vals)
        if status == 'success':
            self._set_transaction_done()
            return True
        elif status == 'failed':
            self._set_transaction_cancel()
            return False
        else:
            self._set_transaction_pending()
            return True

    def _create_paystack_transaction(self):
        self.ensure_one()
        if not self.partner_id.email:
            raise ValidationError(_('Customer email is required for Paystack payments.'))
        # Prepare payload
        payload = {
            'email': self.partner_id.email,
            'amount': int(self.amount * 100),  # kobo
            'reference': self.reference,
            'callback_url': urls.url_join(
                self.provider_id.get_base_url(),
                '/payment/paystack/return?reference=%s' % self.reference
            ),
            'metadata': {
                'order_id': self.reference,
            },
        }
        # Initialize transaction via acquirer helper
        response = self.provider_id._paystack_make_request(
            endpoint='transaction/initialize', json=payload, method='POST'
        )
        if not response.get('status'):
            raise ValidationError(_('Error initializing Paystack payment: %s') % response.get('message'))
        data = response.get('data', {})
        # Store Paystack data
        self.write({
            'paystack_payment_url': data.get('authorization_url'),
            'paystack_reference': data.get('reference'),
        })
        return data.get('authorization_url')

    def paystack_verify_payment(self):
        self.ensure_one()
        if not self.paystack_reference:
            raise ValidationError(_('No Paystack reference available to verify.'))
        # Verify via API
        response = self.acquirer_id._paystack_make_request(
            f'transaction/verify/{self.paystack_reference}', method='GET'
        )
        if not response.get('status'):
            return False
        data = response.get('data', {})
        if data.get('status') == 'success':
            self.write({'provider_reference': data.get('id')})
            self._set_transaction_done()
            return True
        return False

