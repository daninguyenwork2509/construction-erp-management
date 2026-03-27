from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, date


class DailyLog(models.Model):
    """Nhật ký công trường - Site Manager tracking daily progress"""
    _name = 'daily.log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Daily Site Log'
    _order = 'date desc, id desc'

    # ============ BASIC INFO ============
    name = fields.Char(
        string='Log Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: 'DL-' + str(int(datetime.now().timestamp()))
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        readonly=True
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        ondelete='cascade',
        readonly=True
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        compute='_compute_sale_order',
        readonly=True
    )

    @api.depends('project_id')
    def _compute_sale_order(self):
        """Get sale order from project"""
        for record in self:
            # Try to find sale order by project name or directly
            record.sale_order_id = False

    # ============ WORK SUMMARY ============
    work_description = fields.Text(
        string='Work Completed Today',
        required=True,
        help='Describe the work done on site today'
    )
    workers_count = fields.Integer(
        string='Number of Workers'
    )
    weather = fields.Selection(
        selection=[
            ('sunny', 'Sunny'),
            ('rainy', 'Rainy'),
            ('cloudy', 'Cloudy'),
            ('foggy', 'Foggy'),
            ('hot', 'Hot'),
            ('cold', 'Cold'),
        ],
        string='Weather'
    )

    # ============ MATERIALS & EQUIPMENT ============
    materials_used = fields.Text(
        string='Materials Used',
        help='Inventory items used today'
    )
    equipment_used = fields.Text(
        string='Equipment Used'
    )

    # ============ ISSUES & RISKS ============
    issues = fields.Text(
        string='Issues/Blockers',
        help='Any problems encountered'
    )
    safety_incidents = fields.Text(
        string='Safety Incidents',
        help='Any safety concerns or incidents'
    )
    risks = fields.Text(
        string='Risk Assessment',
        help='Potential risks for upcoming work'
    )

    # ============ PHOTOS ============
    photo_ids = fields.Many2many(
        'ir.attachment',
        'daily_log_attachment_rel',
        'log_id',
        'attachment_id',
        string='Site Photos',
        help='Daily progress photos'
    )

    # ============ APPROVAL ============
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved by PM'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        readonly=True
    )
    created_by_id = fields.Many2one(
        'res.users',
        string='Created By',
        readonly=True,
        default=lambda self: self.env.user
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True
    )
    approved_date = fields.Datetime(
        string='Approved Date',
        readonly=True
    )
    approval_notes = fields.Text(
        string='PM Notes',
        readonly=True
    )

    @api.model
    def create(self, vals_list):
        """Auto-generate name if not provided"""
        for vals in (vals_list if isinstance(vals_list, list) else [vals_list]):
            if not vals.get('name'):
                vals['name'] = 'DL-' + str(int(datetime.now().timestamp()))
        return super().create(vals_list)

    def action_submit(self):
        """Submit log for PM approval"""
        self.ensure_one()

        if self.state != 'draft':
            raise ValidationError("Only draft logs can be submitted")

        if not self.work_description:
            raise ValidationError("Work description is required")

        self.state = 'submitted'

    def action_approve(self, notes=''):
        """PM approves the daily log"""
        self.ensure_one()

        if self.state != 'submitted':
            raise ValidationError("Only submitted logs can be approved")

        self.state = 'approved'
        self.approved_by_id = self.env.user.id
        self.approved_date = datetime.now()
        self.approval_notes = notes

    def action_reject(self, notes=''):
        """PM rejects the daily log"""
        self.ensure_one()

        if self.state != 'submitted':
            raise ValidationError("Only submitted logs can be rejected")

        self.state = 'rejected'
        self.approval_notes = notes
