from odoo import models, fields


class BOQJob(models.Model):
    """Công tác thi công (Level 2) - Xây tường, Trát trần, etc."""
    _name = 'boq.job'
    _description = 'BOQ Job (Level 2)'
    _order = 'sequence, id'

    name = fields.Char(
        string='Tên Công tác',
        required=True,
        help='VD: Xây tường, Trát trần, Cài cửa'
    )
    category_id = fields.Many2one(
        comodel_name='boq.category',
        string='Thuộc Hạng mục (Level 1)',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(
        string='Thứ tự',
        default=10
    )
    description = fields.Text(
        string='Mô tả kỹ thuật'
    )
    unit = fields.Char(
        string='Đơn vị tính',
        default='m2',
        help='m2, m, cái, bộ, etc.'
    )

    # Quan hệ ngược: Các dòng báo giá (Level 3) thuộc Công tác này
    order_line_ids = fields.One2many(
        comodel_name='sale.order.line',
        inverse_name='job_id',
        string='Chi tiết Báo giá (Level 3)'
    )
