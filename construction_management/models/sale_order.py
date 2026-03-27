from odoo import models, fields, api
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    """Mở rộng Sale Order cho module Quản lý Xây dựng"""
    _inherit = 'sale.order'

    # Custom Fields
    construction_type = fields.Selection(
        selection=[
            ('civil_structural', 'Xây dựng Cơ bản & Kết cấu (Civil & Structural)'),
            ('fitout_renovation', 'Hoàn thiện & Cải tạo (Fit-out & Renovation)'),
            ('decoration', 'Trang trí & Lắp đặt (Decoration & Event)'),
        ],
        string='Loại hình thi công',
        required=True,
        help='Phân loại loại hình thi công theo chuẩn quốc tế'
    )
    project_address = fields.Char(
        string='Địa chỉ công trình',
        required=True,
        help='Địa chỉ thi công - Bắt buộc nhập trước khi yêu cầu khảo sát'
    )
    estimated_budget = fields.Float(
        string='Ngân sách dự kiến',
        help='Ngân sách ước tính ban đầu'
    )
    customer_notes = fields.Text(
        string='Ghi chú nhu cầu khách hàng',
        help='Ghi chú nhu cầu của khách hàng (VD: Điểm yếu cần khắc phục, ưu tiên, timeline, etc.)'
    )
    pm_id = fields.Many2one(
        comodel_name='res.users',
        string='PM Phụ trách duyệt',
        help='Project Manager duyệt giá'
    )

    # Master Project (Created in BƯỚC 8 - Milestone & Project)
    project_id = fields.Many2one(
        comodel_name='project.project',
        string='Master Project',
        readonly=True,
        help='Tự động tạo khi SO chốt và thanh toán cọc 30%'
    )

    # Quan hệ ngược: Các BOQ Category thuộc Báo giá này
    boq_category_ids = fields.One2many(
        comodel_name='boq.category',
        inverse_name='order_id',
        string='Hạng mục (BOQ Level 1)'
    )

    # Quan hệ ngược: Các Task Khảo sát/Thiết kế
    task_ids = fields.One2many(
        comodel_name='project.task',
        compute='_compute_task_ids',
        string='Tasks liên quan'
    )

    @api.depends('name')
    def _compute_task_ids(self):
        """Tìm tất cả task liên kết với SO này (trong các mở rộng sau)"""
        for record in self:
            record.task_ids = self.env['project.task'].search([
                ('sale_order_id', '=', record.id)
            ])

    # ==================== ACTIONS ====================

    def action_request_survey(self):
        """
        Yêu cầu Khảo sát hiện trạng.
        - Logic: Tạo Task Khảo sát với description là tên loại hình thi công
        - Chuyển state sang 'surveying'
        """
        self.ensure_one()

        if self.state != 'lead':
            raise UserError(f"Chỉ được phép Yêu cầu Khảo sát khi trạng thái là 'lead'. Hiện tại: {self.state}")

        # Lấy tên loại hình thi công (từ selection value)
        construction_type_label = dict(self._fields['construction_type'].selection).get(
            self.construction_type,
            self.construction_type
        )

        # Tạo Task Khảo sát - Đơn giản, chỉ điền description với tên loại hình
        task_survey = self.env['project.task'].create({
            'name': f'Khảo sát: {self.name}',
            'sale_order_id': self.id,
            'task_stage_type': 'survey',
            'description': f'Khảo sát hiện trạng cho loại hình: {construction_type_label}',
        })

        # Chuyển state sang 'surveying'
        self.state = 'surveying'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': task_survey.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_pm_approve(self):
        """
        PM Duyệt Giá - Chỉ user có quyền PM mới được thực hiện.
        - Điều kiện: State phải là 'waiting_pm' + User phải là pm_id
        - Hành động: Chuyển sang 'draft'
        """
        self.ensure_one()

        if self.state != 'waiting_pm':
            raise UserError(f"Chỉ được phép Duyệt Giá khi trạng thái là 'waiting_pm'. Hiện tại: {self.state}")

        # Kiểm tra quyền PM
        if self.pm_id and self.pm_id.id != self.env.user.id:
            raise UserError(f"Chỉ PM '{self.pm_id.name}' được phép duyệt báo giá này!")

        self.state = 'draft'

    def _check_payment_50_percent(self):
        """
        Tự động kích hoạt khi có thanh toán.
        Logic: Nếu total_paid >= 50% amount_total -> Chuyển sang 'sale', tạo Task Thiết kế
        """
        for record in self:
            if record.state not in ['draft', 'sent', 'waiting_pm']:
                continue

            total_paid = sum(payment.amount for payment in record.payment_ids if payment.state == 'posted')
            threshold_50 = record.amount_total * 0.5

            if total_paid >= threshold_50 and record.state != 'sale':
                record.state = 'sale'

                # Lấy tên loại hình thi công
                construction_type_label = dict(record._fields['construction_type'].selection).get(
                    record.construction_type,
                    record.construction_type
                )

                # Tạo Task Thiết kế - Đơn giản, chỉ điền description
                task_design = self.env['project.task'].create({
                    'name': f'Thiết kế: {record.name}',
                    'sale_order_id': record.id,
                    'task_stage_type': 'design',
                    'description': f'Thiết kế bản vẽ cho loại hình: {construction_type_label}',
                })

    def _check_payment_100_percent(self):
        """
        Tự động kích hoạt khi có thanh toán.
        Logic: Nếu total_paid == amount_total -> Chuyển sang 'done'
        """
        for record in self:
            if record.state not in ['sale']:
                continue

            total_paid = sum(payment.amount for payment in record.payment_ids if payment.state == 'posted')

            if total_paid >= record.amount_total and record.state != 'done':
                record.state = 'done'

    @api.model
    def create(self, vals):
        """Override create cho construction_management"""
        result = super().create(vals)
        return result
