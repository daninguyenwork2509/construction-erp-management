from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class Defect(models.Model):
    """Tracking lỗi chất lượng - Quality Defect Management"""
    _name = 'quality.defect'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Quality Defect'
    _order = 'date_reported desc, id desc'

    # ============ IDENTIFICATION ============
    name = fields.Char(
        string='Defect ID',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: 'DEF-' + str(int(datetime.now().timestamp()))
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        ondelete='cascade'
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
            record.sale_order_id = False
    task_id = fields.Many2one(
        'project.task',
        string='Task/Package',
        ondelete='set null'
    )

    # ============ DEFECT DETAILS ============
    description = fields.Text(
        string='Defect Description',
        required=True,
        help='Detailed description of the defect'
    )
    severity = fields.Selection(
        selection=[
            ('critical', 'Critical - Stop Work'),
            ('high', 'High - Urgent Fix Required'),
            ('medium', 'Medium - Should Be Fixed'),
            ('low', 'Low - Minor Issue'),
        ],
        string='Severity Level',
        required=True,
        default='medium'
    )
    category = fields.Selection(
        selection=[
            ('design', 'Design Issue'),
            ('material', 'Material Quality'),
            ('workmanship', 'Workmanship'),
            ('dimension', 'Dimension/Measurement'),
            ('finish', 'Surface Finish'),
            ('safety', 'Safety Issue'),
            ('other', 'Other'),
        ],
        string='Defect Category',
        required=True
    )

    # ============ LOCATION ============
    location = fields.Char(
        string='Location on Site',
        help='Specific location of defect on site'
    )
    boq_job_id = fields.Many2one(
        'boq.job',
        string='BOQ Job Item',
        help='Related BOQ job that has the defect'
    )

    # ============ PHOTO EVIDENCE ============
    photo_ids = fields.Many2many(
        'ir.attachment',
        'defect_photo_rel',
        'defect_id',
        'attachment_id',
        string='Defect Photos',
        help='Before/After photos of defect'
    )

    # ============ WORKFLOW ============
    date_reported = fields.Datetime(
        string='Date Reported',
        required=True,
        default=fields.Datetime.now,
        readonly=True
    )
    reported_by_id = fields.Many2one(
        'res.users',
        string='Reported By',
        readonly=True,
        default=lambda self: self.env.user
    )

    state = fields.Selection(
        selection=[
            ('reported', 'Reported'),
            ('under_review', 'Under Review'),
            ('approved', 'Approved for Fix'),
            ('in_progress', 'Being Fixed'),
            ('completed', 'Fixed & Closed'),
            ('rejected', 'Rejected'),
            ('pending_clarification', 'Pending Clarification'),
        ],
        string='Status',
        default='reported',
        readonly=True
    )

    # ============ RESOLUTION ============
    root_cause = fields.Text(
        string='Root Cause Analysis',
        help='Analysis of why the defect occurred'
    )
    corrective_action = fields.Text(
        string='Corrective Action',
        help='What action will be taken to fix the defect'
    )
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsible For Fix',
        help='Person/team responsible for fixing the defect'
    )
    fix_deadline = fields.Date(
        string='Target Fix Date'
    )

    # ============ CLOSURE ============
    date_fixed = fields.Datetime(
        string='Date Fixed',
        readonly=True
    )
    fixed_by_id = fields.Many2one(
        'res.users',
        string='Fixed By',
        readonly=True
    )
    qa_approval_by_id = fields.Many2one(
        'res.users',
        string='QA Approved By',
        readonly=True,
        help='PM/QA person who verified the fix'
    )
    qa_approval_date = fields.Datetime(
        string='QA Approval Date',
        readonly=True
    )
    qa_notes = fields.Text(
        string='QA Notes',
        readonly=True
    )

    def action_mark_under_review(self):
        """Mark as under review"""
        self.ensure_one()
        self.state = 'under_review'

    def action_approve_fix(self, responsible_id=None, deadline=None):
        """Approve for fixing"""
        self.ensure_one()

        if self.state not in ['reported', 'under_review', 'pending_clarification']:
            raise ValidationError("Can only approve defects that are reported/under review")

        self.state = 'approved'
        if responsible_id:
            self.responsible_id = responsible_id
        if deadline:
            self.fix_deadline = deadline

    def action_mark_in_progress(self):
        """Mark as being fixed"""
        self.ensure_one()

        if self.state != 'approved':
            raise ValidationError("Defect must be approved before marking in progress")

        self.state = 'in_progress'

    def action_mark_completed(self, qa_notes=''):
        """Mark as completed/fixed"""
        self.ensure_one()

        if self.state != 'in_progress':
            raise ValidationError("Defect must be in progress before marking as completed")

        self.state = 'completed'
        self.date_fixed = datetime.now()
        self.fixed_by_id = self.env.user.id
        self.qa_approval_by_id = self.env.user.id
        self.qa_approval_date = datetime.now()
        self.qa_notes = qa_notes

    def action_reject(self, notes=''):
        """Reject the defect claim"""
        self.ensure_one()

        if self.state == 'completed':
            raise ValidationError("Cannot reject a completed defect")

        self.state = 'rejected'
        self.qa_notes = notes

    def action_request_clarification(self, notes=''):
        """Request more information about the defect"""
        self.ensure_one()

        if self.state != 'reported':
            raise ValidationError("Can only request clarification for newly reported defects")

        self.state = 'pending_clarification'
        self.qa_notes = notes
