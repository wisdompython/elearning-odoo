# -*- coding: utf-8 -*-

from odoo import models, fields, api
import hashlib
import hmac
import logging
import requests
import json
from werkzeug import urls

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_repr

_logger = logging.getLogger(__name__)


# class payment_paystack(models.Model):
#     _name = 'payment_paystack.payment_paystack'
#     _description = 'payment_paystack.payment_paystack'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('paystack', 'Paystack')],
        ondelete={'paystack': 'set default'}
    )
    paystack_secret_key = fields.Char(
        string='Paystack Secret Key',
        help='The secret key provided by Paystack',
        required_if_provider='paystack',
        groups='base.group_system'
    )
    paystack_public_key = fields.Char(
        string='Paystack Public Key',
        help='The public key provided by Paystack',
        required_if_provider='paystack',
        groups='base.group_system'
    )

    def _get_paystack_api_url(self):
        """Return the API URL according to the provider state.

        Note: self.ensure_one()

        :return: The API URL
        :rtype: str
        """
        self.ensure_one()
        if self.state == 'enabled':
            return 'https://api.paystack.co'
        else:
            return 'https://api.paystack.co'  # Paystack doesn't have a test API URL

    def _paystack_make_request(self, endpoint, payload=None, method='POST'):
        """Make a request to Paystack API at the specified endpoint.

        Note: self.ensure_one()

        :param str endpoint: The endpoint to be reached by the request
        :param dict payload: The payload of the request
        :param str method: The HTTP method of the request
        :return The JSON-formatted content of the response
        :rtype: dict
        :raise: ValidationError if an HTTP error occurs
        """
        self.ensure_one()
        url = f"{self._get_paystack_api_url()}/{endpoint.strip('/')}"
        headers = {
            'Authorization': f'Bearer {self.paystack_secret_key}',
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
        }

        try:
            if method == 'GET':
                response = requests.get(url, params=payload, headers=headers, timeout=60)
            else:
                response = requests.post(
                    url,
                    headers=headers,
                    data=json.dumps(payload) if payload else None,
                    timeout=60
                )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            _logger.error("Unable to reach endpoint at %s", url)
            raise ValidationError("Could not establish the connection to Paystack.")
        except requests.exceptions.HTTPError as error:
            _logger.error("Invalid API request at %s with data %s: %s", url, payload, error.response.text)
            raise ValidationError("Paystack: " + error.response.text)
        except (ValueError, requests.exceptions.Timeout) as error:
            _logger.error("Invalid API response at %s with data %s: %s", url, payload, str(error))
            raise ValidationError("Paystack: " + str(error))

    def _get_default_payment_method_id(self):
        self.ensure_one()
        if self.code != 'paystack':
            return super()._get_default_payment_method_id()
        return self.env.ref('payment_paystack.payment_method_paystack').id

    def _should_build_inline_form(self, is_validation=False):
        if self.code == 'paystack':
            return True
        return super()._should_build_inline_form(is_validation)

    def _paystack_format_amount(self, amount, currency):
        """Convert the amount to kobo (smallest currency unit in Nigeria).

        :param float amount: The amount to convert
        :param recordset currency: The currency of the amount
        :return: The amount in kobo
        :rtype: int
        """
        self.ensure_one()
        return int(amount * 100)

    def paystack_form_generate_values(self, values):
        self.ensure_one()
        
        base_url = self.get_base_url()
        paystack_tx_values = dict(values)
        
        # Create a reference
        tx_reference = f"tx-{values.get('reference')}"
        paystack_tx_values.update({
            'key': self.paystack_public_key,
            'email': values.get('partner_email'),
            'amount': int(values.get('amount') * 100),  # Paystack expects amount in kobo (smallest unit)
            'currency': values.get('currency').name,
            'reference': tx_reference,
            'callback_url': urls.url_join(base_url, '/payment/paystack/return'),
            'metadata': {
                'order_id': values.get('reference'),
                'customer_name': values.get('partner_name'),
                'customer_email': values.get('partner_email'),
            }
        })
        return paystack_tx_values

    def paystack_get_form_action_url(self):
        self.ensure_one()
        return '/payment/paystack/checkout'
