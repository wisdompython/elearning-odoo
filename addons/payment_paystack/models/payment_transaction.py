# -*- coding: utf-8 -*-

import logging
from werkzeug import urls

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    paystack_reference = fields.Char(
        string='Paystack Reference',
        help='The reference of the transaction in Paystack',
        readonly=True
    )
    paystack_payment_url = fields.Char(
        string='Paystack Payment URL',
        help='The URL to redirect the customer to complete the payment',
        readonly=True
    )

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Paystack-specific rendering values.

        Note: self.ensure_one() from base method

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'paystack':
            return res

        # Initiate payment and get authorization URL
        payload = {
            'email': self.partner_email,
            'amount': self.provider_id._paystack_format_amount(self.amount, self.currency_id),
            'currency': self.currency_id.name,
            'reference': self.reference,
            'callback_url': urls.url_join(
                self.provider_id.get_base_url(),
                '/payment/paystack/return'
            ),
            'metadata': {
                'transaction_reference': self.reference,
                'customer_name': self.partner_name,
                'customer_email': self.partner_email,
            }
        }
        response = self.provider_id._paystack_make_request(
            'transaction/initialize',
            payload=payload
        )
        if not response.get('status'):
            raise ValidationError(
                "Paystack: " + response.get('message', _("Could not initiate payment."))
            )

        return {
            'api_url': response['data']['authorization_url'],
            'reference': self.reference,
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of payment to find the transaction based on Paystack data.

        :param str provider_code: The code of the provider that handled the transaction
        :param dict notification_data: The notification data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'paystack' or len(tx) == 1:
            return tx

        reference = notification_data.get('reference')
        if not reference:
            raise ValidationError("Paystack: Missing reference in notification data.")

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'paystack')])
        if not tx:
            raise ValidationError(
                "Paystack: No transaction found with reference %s." % reference
            )
        return tx

    def _process_notification_data(self, notification_data):
        """ Override of payment to process the transaction based on Paystack data.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider
        :return: None
        :raise: ValidationError if inconsistent data were received
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'paystack':
            return

        # Verify payment with Paystack
        self._verify_paystack_payment(notification_data)

    def _verify_paystack_payment(self, notification_data):
        """ Verify the payment status with Paystack.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider
        :return: None
        :raise: ValidationError if inconsistent data were received
        """
        self.ensure_one()

        # Fetch transaction details from Paystack
        reference = notification_data.get('reference')
        response = self.provider_id._paystack_make_request(
            f'transaction/verify/{reference}',
            method='GET'
        )

        if not response.get('status'):
            raise ValidationError(
                "Paystack: " + response.get('message', _("Could not verify payment."))
            )

        data = response.get('data', {})
        if not data:
            raise ValidationError("Paystack: No data received from verification request.")

        # Check payment status
        status = data.get('status')
        if status == 'success':
            self._set_done()
            self.provider_reference = data.get('id')
        elif status == 'failed':
            self._set_canceled()
        else:
            _logger.info(
                "Received data with invalid payment status (%s) for transaction with "
                "reference %s", status, self.reference
            )
            self._set_error("Paystack: Invalid payment status: %s" % status)

