from odoo import models, fields, api, _

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'
    
    subscription_id = fields.Many2one('elearning.subscription', string='Related Subscription')
    
    def _process_subscription_payment(self, subscription):
        """Process payment for a subscription"""
        # Link subscription to transaction
        self.write({'subscription_id': subscription.id})
        
    def _reconcile_after_done(self):
        """Automatically activate subscription after successful payment"""
        res = super()._reconcile_after_done()
        
        # Check for subscription payments
        for tx in self.filtered(lambda t: t.subscription_id and t.state == 'done'):
            tx.subscription_id.action_activate()
            
        return res

class PaymentLinkWizard(models.TransientModel):
    _inherit = 'payment.link.wizard'
    
    subscription_id = fields.Many2one('elearning.subscription', string='Subscription')
    description = fields.Text(string="Description")  # ← add this if needed
    
    @api.onchange('subscription_id')
    def _onchange_subscription_id(self):
        """Update amount based on subscription plan"""
        if self.subscription_id:
            self.amount = self.subscription_id.plan_id.price
            self.currency_id = self.subscription_id.plan_id.currency_id