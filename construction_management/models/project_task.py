from odoo import models, fields, api
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    """Mở rộng Project Task cho Khảo sát và Thiết kế"""
    _inherit = 'project.task'

    # Custom Fields
    task_stage_type = fields.Selection(
        selection=[
            ('survey', 'Khảo sát hiện trạng'),
            ('design', 'Thiết kế bản vẽ'),
            ('execution', 'Thi công'),
        ],
        string='Phân loại Task',
        help='Phân loại loại task'
    )
    is_survey_data_locked = fields.Boolean(
        string='Khóa dữ liệu khảo sát',
        default=False,
        help='Nếu checked, dữ liệu khảo sát không được sửa'
    )
    design_file_type = fields.Selection(
        selection=[
            ('draft', 'Bản Nháp (Watermark)'),
            ('final', 'File Gốc (CAD/PDF)'),
        ],
        string='Loại File Upload',
        help='Loại file được phép upload'
    )

    # Quan hệ ngược: Liên kết với Sale Order
    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Thuộc Báo giá/Hợp đồng',
        help='Báo giá/Hợp đồng liên quan đến task này'
    )

    # ==================== ACTIONS ====================

    def action_close_survey_task(self):
        """
        Hoàn Thành Khảo Sát.
        - Điều kiện: Bắt buộc có file đính kèm, task type phải là 'survey'
        - Hành động: Đóng task, cập nhật Sale Order sang 'waiting_pm'
        """
        self.ensure_one()

        if self.task_stage_type != 'survey':
            raise UserError("Chỉ có thể đóng Task Khảo sát nếu task_stage_type = 'survey'")

        # Kiểm tra bắt buộc upload file
        attachment_count = self.env['ir.attachment'].search_count([
            ('res_model', '=', 'project.task'),
            ('res_id', '=', self.id),
        ])

        if attachment_count == 0:
            raise UserError(
                "Bắt buộc phải upload file hiện trạng trước khi đóng Task Khảo sát!\n"
                "Vui lòng đính kèm file khảo sát (ảnh, bản vẽ hiện trạng, etc.)"
            )

        # Đóng task
        self.stage_id = self.env['project.task.type'].search([
            ('name', '=', 'Done'),
        ], limit=1)

        # Cập nhật Sale Order sang 'waiting_pm'
        if self.sale_order_id:
            self.sale_order_id.state = 'waiting_pm'

    def action_upload_design_file(self):
        """
        Xác Nhận Up File & Đóng Task Thiết kế.
        - Điều kiện: Kiểm tra trạng thái thanh toán của Sale Order
        - Logic: Nếu chưa trả 100%, chỉ cho phép up draft. Nếu final, báo lỗi.
        """
        self.ensure_one()

        if not self.sale_order_id:
            raise UserError("Task này chưa liên kết với Sale Order nào!")

        so = self.sale_order_id
        total_paid = sum(
            payment.amount for payment in so.payment_ids
            if payment.state == 'posted'
        )
        is_fully_paid = total_paid >= so.amount_total

        # Logic chặn: Nếu chưa trả đủ tiền, không được phép up file 'final'
        if not is_fully_paid and self.design_file_type == 'final':
            raise UserError(
                "Chưa thanh toán đủ 100%, chỉ được phép up Bản Nháp!\n"
                f"Tổng tiền: {so.amount_total}\n"
                f"Đã thanh toán: {total_paid}"
            )

        # Nếu hợp lệ, đóng task
        self.stage_id = self.env['project.task.type'].search([
            ('name', '=', 'Done'),
        ], limit=1)

    def action_lock_survey_data(self):
        """Khóa dữ liệu khảo sát sau khi hoàn thành"""
        self.ensure_one()
        self.is_survey_data_locked = True

    def action_unlock_survey_data(self):
        """Mở khóa dữ liệu khảo sát (chỉ PM được phép)"""
        self.ensure_one()
        if not self.env.user.has_group('project.group_project_manager'):
            raise UserError("Chỉ Project Manager được phép mở khóa dữ liệu khảo sát!")
        self.is_survey_data_locked = False

    @api.constrains('is_survey_data_locked')
    def _check_survey_data_locked(self):
        """Nếu dữ liệu bị khóa, không được phép chỉnh sửa task"""
        for record in self:
            if record.is_survey_data_locked and record.task_stage_type == 'survey':
                # Có thể thêm logic ngăn chặn edit ở đây nếu cần
                pass
