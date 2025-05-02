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
    _name = 'payment.provider'
    _inherits = "payment.provider"

    provider = fields.Selection(selection_add=[('paystack', 'Paystack')], ondelete={'paystack': 'set default'})
    paystack_secret_key = fields.Char(string='Paystack Secret Key', required_if_provider='paystack', groups='base.group_user')
    paystack_public_key = fields.Char(string='Paystack Public Key', required_if_provider='paystack', groups='base.group_user')


    def _get_paystack_url(self):
        self.ensure_one()

        return 'https://api.paystack.co'
    
    def _paystack_make_request(self, endpoint, payload=None, method='POST'):
        """Make a request to Paystack API at the specified endpoint.
        
        Note: Authentication to the API is performed through the Authorization header,
        with a bearer token using your secret key.
        """
        self.ensure_one()
        url = f"{self._get_paystack_url()}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.paystack_secret_key}',
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
        }
        
        try:
            if method == 'POST':
                response = requests.post(url, headers=headers, data=json.dumps(payload) if payload else None, timeout=60)
            elif method == 'GET':
                response = requests.get(url, headers=headers, params=payload, timeout=60)
            else:
                raise ValidationError(_("Method not supported"))
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            raise ValidationError(_("Could not establish the connection to Paystack."))
        except requests.exceptions.HTTPError as e:
            raise ValidationError(_("Paystack: %s") % e.response.text)
        except (ValueError, requests.exceptions.Timeout) as e:
            raise ValidationError(_("Paystack: %s") % str(e))
    

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
