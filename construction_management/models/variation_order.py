from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError
import secrets
import hashlib
from datetime import datetime


class VariationOrder(models.Model):
    """Mở rộng VO - Yêu cầu thay đổi công trình với phê duyệt của KH"""
    _name = 'variation.order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Variation Order (VO) - Change Order'
    _order = 'id desc'

    # ============ BASIC INFO ============
    name = fields.Char(
        string='VO Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: 'VO-' + str(int(datetime.now().timestamp()))
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        ondelete='cascade',
        readonly=True
    )
    description = fields.Text(
        string='Change Description',
        required=True
    )
    reason = fields.Selection(
        selection=[
            ('scope_change', 'Scope Change'),
            ('design_change', 'Design Change'),
            ('material_change', 'Material Change'),
            ('schedule_change', 'Schedule Change'),
            ('budget_increase', 'Budget Increase'),
            ('other', 'Other'),
        ],
        string='Reason for Change',
        required=True
    )

    # ============ COST IMPACT ============
    original_amount = fields.Monetary(
        string='Original Amount',
        compute='_compute_original_amount',
        readonly=True,
        currency_field='currency_id'
    )
    change_amount = fields.Monetary(
        string='Additional Cost',
        required=True,
        currency_field='currency_id'
    )
    total_amount = fields.Monetary(
        string='New Total Amount',
        compute='_compute_total_amount',
        readonly=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='sale_order_id.currency_id',
        readonly=True
    )

    # ============ WORKFLOW STATE ============
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted to Customer'),
            ('customer_approved', 'Customer Approved'),
            ('customer_rejected', 'Customer Rejected'),
            ('done', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        readonly=True
    )

    # ============ CUSTOMER APPROVAL (Portal Link) ============
    approval_token = fields.Char(
        string='Approval Token',
        default=lambda self: secrets.token_urlsafe(32),
        readonly=True,
        copy=False,
        help='Token to verify customer approval via link'
    )
    approval_url = fields.Char(
        string='Customer Approval Link',
        compute='_compute_approval_url',
        readonly=True,
        help='Link for customer to approve/reject VO'
    )
    customer_approval_phone = fields.Char(
        string='Customer Phone (for verification)',
        readonly=True,
        help='Phone number used to verify customer approval'
    )
    is_customer_approved = fields.Boolean(
        string='Customer Approved?',
        default=False,
        readonly=True
    )
    customer_approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True
    )
    customer_approval_ip = fields.Char(
        string='Approval IP',
        readonly=True,
        help='IP address of customer when approving'
    )

    # ============ AUDIT TRAIL ============
    created_by_id = fields.Many2one(
        'res.users',
        string='Created By',
        readonly=True,
        default=lambda self: self.env.user
    )
    submitted_by_id = fields.Many2one(
        'res.users',
        string='Submitted By',
        readonly=True
    )
    submitted_date = fields.Datetime(
        string='Submitted Date',
        readonly=True
    )
    approval_notes = fields.Text(
        string='Customer Approval Notes',
        readonly=True,
        help='Notes from customer during approval'
    )

    @api.depends('sale_order_id.amount_total')
    def _compute_original_amount(self):
        """Get original amount from sale order"""
        for record in self:
            record.original_amount = record.sale_order_id.amount_total if record.sale_order_id else 0

    @api.depends('original_amount', 'change_amount')
    def _compute_total_amount(self):
        """Calculate new total after change"""
        for record in self:
            record.total_amount = record.original_amount + record.change_amount

    @api.depends('approval_token')
    def _compute_approval_url(self):
        """Generate customer approval portal URL"""
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url',
            default='http://localhost:8070'
        )
        for record in self:
            if record.id:
                record.approval_url = (
                    f"{base_url}/vo/approve/{record.id}?"
                    f"token={record.approval_token}"
                )
            else:
                record.approval_url = ''

    def action_submit_to_customer(self):
        """Submit VO to customer for approval via link"""
        self.ensure_one()

        if self.state != 'draft':
            raise ValidationError("Only draft VOs can be submitted")

        self.state = 'submitted'
        self.submitted_by_id = self.env.user.id
        self.submitted_date = datetime.now()

        # TODO: Send email/SMS to customer with approval link
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'VO {self.name} submitted to customer',
                'type': 'success',
            }
        }

    def action_approve(self, phone_number, notes='', ip_address='127.0.0.1'):
        """
        Customer approval via portal link
        Params:
            phone_number: Customer phone for verification
            notes: Optional approval notes
            ip_address: IP of approving customer
        """
        self.ensure_one()

        if self.state != 'submitted':
            raise ValidationError("Only submitted VOs can be approved")

        # Record approval
        self.is_customer_approved = True
        self.state = 'customer_approved'
        self.customer_approval_date = datetime.now()
        self.customer_approval_phone = phone_number
        self.customer_approval_ip = ip_address
        self.approval_notes = notes

        return True

    def action_reject(self, phone_number, notes='', ip_address='127.0.0.1'):
        """
        Customer rejection via portal link
        """
        self.ensure_one()

        if self.state != 'submitted':
            raise ValidationError("Only submitted VOs can be rejected")

        self.state = 'customer_rejected'
        self.customer_approval_date = datetime.now()
        self.customer_approval_phone = phone_number
        self.customer_approval_ip = ip_address
        self.approval_notes = notes

        return True

    def action_complete(self):
        """Mark VO as completed"""
        self.ensure_one()

        if not self.is_customer_approved:
            raise ValidationError("VO must be approved by customer before completion")

        self.state = 'done'

        # TODO: Update sale order amount if approved
        # self.sale_order_id.amount_total += self.change_amount

    def action_cancel(self):
        """Cancel the VO"""
        self.ensure_one()

        if self.state == 'done':
            raise ValidationError("Cannot cancel completed VO")

        self.state = 'cancelled'
