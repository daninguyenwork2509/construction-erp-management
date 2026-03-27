from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class QCChecklistTemplate(models.Model):
    """QC Checklist Template - Reusable quality check templates"""
    _name = 'qc.checklist.template'
    _description = 'QC Checklist Template'

    name = fields.Char(
        string='Template Name',
        required=True
    )
    description = fields.Text(
        string='Description'
    )
    construction_type = fields.Selection(
        selection=[
            ('civil_structural', 'Civil & Structural'),
            ('fitout_renovation', 'Fit-out & Renovation'),
            ('decoration', 'Decoration & Event'),
        ],
        string='Construction Type',
        help='Applicable construction type'
    )
    item_ids = fields.One2many(
        'qc.checklist.item',
        'template_id',
        string='Checklist Items'
    )

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Template name must be unique!')
    ]


class QCChecklistItem(models.Model):
    """Individual QC checklist item"""
    _name = 'qc.checklist.item'
    _description = 'QC Checklist Item'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    template_id = fields.Many2one(
        'qc.checklist.template',
        string='Template',
        ondelete='cascade'
    )
    checklist_id = fields.Many2one(
        'qc.checklist',
        string='Checklist',
        ondelete='cascade'
    )
    name = fields.Char(
        string='Item Name',
        required=True
    )
    category = fields.Char(
        string='Category',
        help='Category of check (e.g., Dimension, Surface, Safety)'
    )
    standard = fields.Text(
        string='Quality Standard',
        help='Expected standard or requirement'
    )
    is_pass = fields.Boolean(
        string='Pass?',
        default=False
    )
    notes = fields.Text(
        string='Notes',
        help='Inspection notes or findings'
    )


class QCChecklist(models.Model):
    """Quality Control Checklist - Actual inspections"""
    _name = 'qc.checklist'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'QC Checklist/Inspection'
    _order = 'date desc, id desc'

    # ============ BASIC INFO ============
    name = fields.Char(
        string='Checklist ID',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: 'QC-' + str(int(datetime.now().timestamp()))
    )
    date = fields.Date(
        string='Inspection Date',
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
            record.sale_order_id = False
    task_id = fields.Many2one(
        'project.task',
        string='Task/Package',
        readonly=True,
        help='Work package being inspected'
    )
    boq_job_id = fields.Many2one(
        'boq.job',
        string='BOQ Job',
        readonly=True
    )

    # ============ TEMPLATE & ITEMS ============
    template_id = fields.Many2one(
        'qc.checklist.template',
        string='Template',
        readonly=True
    )
    item_ids = fields.One2many(
        'qc.checklist.item',
        'checklist_id',
        string='Inspection Items'
    )

    # ============ RESULTS ============
    total_items = fields.Integer(
        string='Total Items',
        compute='_compute_totals'
    )
    pass_items = fields.Integer(
        string='Pass Items',
        compute='_compute_totals'
    )
    fail_items = fields.Integer(
        string='Fail Items',
        compute='_compute_totals'
    )
    pass_percentage = fields.Float(
        string='Pass %',
        compute='_compute_totals'
    )
    overall_result = fields.Selection(
        selection=[
            ('pass', 'PASS - All items acceptable'),
            ('conditional', 'CONDITIONAL - Minor issues'),
            ('fail', 'FAIL - Major issues'),
        ],
        string='Overall Result',
        readonly=True,
        compute='_compute_overall_result'
    )

    # ============ GENERAL NOTES ============
    general_notes = fields.Text(
        string='General Comments'
    )
    corrective_actions = fields.Text(
        string='Required Corrective Actions'
    )

    # ============ SIGNATURES ============
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('approved', 'Approved'),
        ],
        string='Status',
        default='draft',
        readonly=True
    )
    inspected_by_id = fields.Many2one(
        'res.users',
        string='Inspected By',
        readonly=True,
        default=lambda self: self.env.user
    )
    inspection_date = fields.Datetime(
        string='Inspection Completed At',
        readonly=True
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True
    )
    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True
    )

    @api.depends('item_ids.is_pass')
    def _compute_totals(self):
        """Calculate pass/fail statistics"""
        for record in self:
            items = record.item_ids
            record.total_items = len(items)
            record.pass_items = len(items.filtered(lambda x: x.is_pass))
            record.fail_items = record.total_items - record.pass_items
            record.pass_percentage = (
                (record.pass_items / record.total_items * 100)
                if record.total_items > 0
                else 0
            )

    @api.depends('pass_percentage', 'fail_items')
    def _compute_overall_result(self):
        """Determine overall pass/fail result"""
        for record in self:
            if record.pass_percentage == 100:
                record.overall_result = 'pass'
            elif record.fail_items > 0 and record.pass_percentage >= 80:
                record.overall_result = 'conditional'
            else:
                record.overall_result = 'fail'

    def action_load_template(self):
        """Load checklist items from template"""
        self.ensure_one()

        if not self.template_id:
            raise ValidationError("Please select a template first")

        # Remove existing items
        self.item_ids.unlink()

        # Copy template items
        for template_item in self.template_id.item_ids:
            self.env['qc.checklist.item'].create({
                'checklist_id': self.id,
                'name': template_item.name,
                'category': template_item.category,
                'standard': template_item.standard,
                'sequence': template_item.sequence,
            })

    def action_start_inspection(self):
        """Start the inspection"""
        self.ensure_one()

        if not self.item_ids:
            raise ValidationError("No items in checklist. Load template or add items manually.")

        self.state = 'in_progress'

    def action_complete_inspection(self):
        """Mark inspection as completed"""
        self.ensure_one()

        if self.state != 'in_progress':
            raise ValidationError("Inspection must be in progress to complete")

        self.state = 'completed'
        self.inspection_date = datetime.now()

    def action_approve(self):
        """PM approves the inspection result"""
        self.ensure_one()

        if self.state != 'completed':
            raise ValidationError("Only completed inspections can be approved")

        self.state = 'approved'
        self.approved_by_id = self.env.user.id
        self.approval_date = datetime.now()

        # If failed, auto-create defect records
        if self.overall_result == 'fail':
            self._create_defects_from_failed_items()

    def _create_defects_from_failed_items(self):
        """Auto-create defect records for failed items"""
        defect_model = self.env['quality.defect']

        for item in self.item_ids.filtered(lambda x: not x.is_pass):
            defect_model.create({
                'project_id': self.project_id.id,
                'task_id': self.task_id.id,
                'boq_job_id': self.boq_job_id.id,
                'description': f"QC Failed: {item.name} - {item.notes}",
                'category': 'workmanship',
                'severity': 'medium',
                'location': self.boq_job_id.name if self.boq_job_id else 'See QC Checklist'
            })
