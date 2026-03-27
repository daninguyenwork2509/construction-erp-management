from odoo import models, fields, api
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    """Mở rộng Sale Order Line cho BOQ 3 Level"""
    _inherit = 'sale.order.line'

    # Custom Fields
    job_id = fields.Many2one(
        comodel_name='boq.job',
        string='Thuộc Công tác (Level 2)',
        help='Bóc tách khối lượng - Chọn công tác để gắn chi phí này'
    )
    is_subcontracted = fields.Boolean(
        string='Giao Thầu phụ',
        default=False,
        help='Đánh dấu nếu công tác này được giao thầu phụ'
    )

    @api.constrains('job_id')
    def _check_job_id_required(self):
        """Ràng buộc: Bắt buộc chọn job_id khi lưu dòng báo giá"""
        for record in self:
            # Bỏ qua nếu là dòng note hoặc section
            if record.display_type in ['line_section', 'line_note']:
                continue

            if not record.job_id:
                raise UserError(
                    "Mỗi chi phí vật tư/nhân công phải được gắn vào một Công tác cụ thể (Level 2).\n"
                    "Vui lòng chọn Công tác (job_id) trước khi lưu!"
                )

    @api.onchange('order_id')
    def _onchange_order_id(self):
        """Khi thay đổi order, reset job_id (vì BOQ categories khác nhau)"""
        self.job_id = False
