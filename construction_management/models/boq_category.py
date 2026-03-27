from odoo import models, fields


class BOQCategory(models.Model):
    """Hạng mục lớn (Level 1) - Phần Thô, MEP, etc."""
    _name = 'boq.category'
    _description = 'BOQ Category (Level 1)'
    _order = 'sequence, id'

    name = fields.Char(
        string='Tên Hạng mục',
        required=True,
        help='VD: Phần Thô, MEP, Trang trí'
    )
    order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Thuộc Báo giá/Hợp đồng',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(
        string='Thứ tự',
        default=10
    )
    description = fields.Text(
        string='Mô tả'
    )

    # Quan hệ ngược: Các Công tác (Level 2) thuộc Hạng mục này
    job_ids = fields.One2many(
        comodel_name='boq.job',
        inverse_name='category_id',
        string='Công tác (Level 2)'
    )
