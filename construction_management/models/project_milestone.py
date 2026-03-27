from odoo import models, fields, api
from odoo.exceptions import AccessError, UserError
from datetime import datetime


class ProjectMilestone(models.Model):
    """Mở rộng Project Milestone - QA Acceptance & Accounting Trigger"""
    _inherit = 'project.milestone'

    # ============ QUALITY ACCEPTANCE ============
    is_reached = fields.Boolean(
        string='Đã Hoàn Thành & Đạt Chất Lượng?',
        default=False,
        readonly=True,
        help='Mốc đã được PM nghiệm thu và xác nhận đạt chất lượng'
    )
    reached_by_id = fields.Many2one(
        'res.users',
        string='Nghiệm Thu Bởi',
        readonly=True,
        help='PM/Director người thực hiện nghiệm thu'
    )
    reached_date = fields.Datetime(
        string='Ngày Giờ Nghiệm Thu',
        readonly=True,
        help='Thời điểm PM xác nhận mốc đạt chất lượng'
    )

    # ============ ACCOUNTING TRIGGER ============
    is_accounting_notified = fields.Boolean(
        string='Đã Thông Báo Kế Toán?',
        default=False,
        readonly=True,
        help='Đã tự động gửi thông báo cho Kế toán sau khi QA'
    )
    accounting_activity_id = fields.Many2one(
        'mail.activity',
        string='Activity Kế Toán',
        readonly=True,
        help='Link tới Activity được gửi cho Kế toán'
    )

    # ============ QA NOTES ============
    qa_notes = fields.Text(
        string='Ghi Chú Nghiệm Thu',
        help='PM ghi chú về chất lượng mốc này (khối lượng, chất lượng, v.v.)'
    )

    @api.constrains('is_reached')
    def _check_milestone_deadline_before_reaching(self):
        """
        Kiểm tra: Nếu is_reached=True thì actual_completion_date phải ≤ deadline
        """
        for record in self:
            if record.is_reached and record.actual_completion_date:
                if record.actual_completion_date > record.deadline:
                    delay_days = (record.actual_completion_date - record.deadline).days
                    # Warning (không block)
                    self.env['mail.message'].create({
                        'subject': f'⚠️ Mốc "{record.name}" hoàn thành trễ {delay_days} ngày',
                        'body': f'Mốc hoàn thành ngày {record.actual_completion_date.date()} '
                               f'> Deadline {record.deadline.date()}',
                        'model': 'project.milestone',
                        'res_id': record.id,
                    })

    def action_accept_milestone(self):
        """
        Nghiệm Thu Mốc (Quality Acceptance by PM/Director).

        Quyền hạn:
        - Chỉ user thuộc nhóm 'Project Manager' hoặc 'Director' được phép
        - Kỹ sư Giám sát KHÔNG được bấm

        Logic:
        1. Check quyền hạn (AccessError nếu không phải PM/Director)
        2. Set is_reached=True
        3. Record reached_by_id=current_user, reached_date=now
        4. Ghi vết (message + audit log)
        5. Trigger: Tạo mail.activity cho Accounting
        """
        self.ensure_one()
        user = self.env.user

        # ============ 1. CHECK QUYỀN HẠN ============
        pm_group = self.env.ref(
            'construction_management.group_project_manager_supervisor',
            raise_if_not_found=False
        )
        director_group = self.env.ref(
            'construction_management.group_construction_manager',
            raise_if_not_found=False
        )

        is_pm = pm_group and user in pm_group.users
        is_director = director_group and user in director_group.users

        if not (is_pm or is_director):
            raise AccessError(
                f"❌ QUY ÒN BỊ TỪ CHỐI!\n\n"
                f"Chỉ có Project Manager hoặc Director mới được phép "
                f"thực hiện Nghiệm Thu Mốc.\n"
                f"Người dùng hiện tại: {user.name}\n"
                f"Nhóm: {', '.join(user.groups_id.mapped('name'))}"
            )

        # ============ 2. SET REACHED STATUS ============
        now = datetime.now()
        self.write({
            'is_reached': True,
            'reached_by_id': user.id,
            'reached_date': now,
        })

        # ============ 3. GHI VẾT ============
        log_message = (
            f"✅ <strong>NGHIỆM THU MỐC</strong><br/>"
            f"<strong>Mốc:</strong> {self.name}<br/>"
            f"<strong>Nghiệm thu bởi:</strong> {user.name}<br/>"
            f"<strong>Lúc:</strong> {now.strftime('%d/%m/%Y %H:%M:%S')}<br/>"
            f"<strong>Ghi chú:</strong> {self.qa_notes or 'Không có'}<br/>"
        )

        self.message_post(
            body=log_message,
            message_type='notification',
            subtype='mail.mt_comment'
        )

        # ============ 4. TRIGGER: WAKE-UP ACCOUNTING ============
        self._trigger_accounting_notification()

        return {'type': 'ir.actions.act_window_close'}

    def _trigger_accounting_notification(self):
        """
        Tự động tạo mail.activity cho Accounting group.
        - Activity type: 'To Do'
        - Assignee: User từ group 'Accounting'
        - Summary: Nội dung cảnh báo
        """
        self.ensure_one()

        # Lấy project
        project = self.project_id
        if not project:
            return

        # Lấy sale order gốc
        sale_order = project.sale_id or self.env['sale.order'].search([
            ('project_id', '=', project.id)
        ], limit=1)

        if not sale_order:
            return

        # Lấy user từ group 'Accounting'
        accounting_group = self.env.ref(
            'account.group_account_invoice',
            raise_if_not_found=False
        )

        if not accounting_group:
            return

        accounting_users = accounting_group.users

        if not accounting_users:
            return

        # Tạo activity cho mỗi Accountant
        activity_type = self.env['mail.activity.type'].search([
            ('name', '=', 'To Do')
        ], limit=1)

        if not activity_type:
            # Fallback: Use first available type
            activity_type = self.env['mail.activity.type'].search([], limit=1)

        for user in accounting_users:
            summary = (
                f"🚨 YÊU CẦU XUẤT HÓA ĐƠN\n"
                f"Mốc: {self.name} | Dự án: {project.name}"
            )

            description = (
                f"<p><strong>🚨 THÔNG BÁO KÍCH HOẠT DÒNG TIỀN</strong></p>"
                f"<p>Mốc thi công: <strong>{self.name}</strong> của Dự án: <strong>{project.name}</strong> "
                f"đã được PM nghiệm thu đạt chất lượng.</p>"
                f"<p><strong>⚠️ HÀNH ĐỘNG CẦN THỰC HIỆN (NGAY):</strong></p>"
                f"<ol>"
                f"  <li>Mở Hợp đồng gốc: {sale_order.name}</li>"
                f"  <li>XUẤT HÓA ĐƠN THU TIỀN khách hàng theo mốc này</li>"
                f"  <li>Cập nhật hóa đơn vào dự án: {project.name}</li>"
                f"</ol>"
                f"<p><strong>Chi tiết Dự án:</strong></p>"
                f"<ul>"
                f"  <li>Khách hàng: {sale_order.partner_id.name}</li>"
                f"  <li>Tổng Hợp đồng: {sale_order.amount_total:,.0f} VND</li>"
                f"  <li>Project Manager: {project.user_id.name}</li>"
                f"</ul>"
                f"<p><em>Hệ thống Quản lý Xây dựng - Auto triggered</em></p>"
            )

            activity = self.env['mail.activity'].create({
                'activity_type_id': activity_type.id if activity_type else False,
                'user_id': user.id,
                'res_model': 'project.milestone',
                'res_id': self.id,
                'summary': summary,
                'note': description,
                'date_deadline': datetime.now().date(),
            })

            # Ghi vết
            self.accounting_activity_id = activity
            self.is_accounting_notified = True

            # Send email notification
            self.message_post(
                body=f"📧 Đã gửi Activity cho Kế toán: {user.name}",
                message_type='notification',
                subtype='mail.mt_comment'
            )

    def action_view_accounting_activity(self):
        """Smart button: Xem Activity gửi cho Kế toán"""
        self.ensure_one()

        if not self.accounting_activity_id:
            return {'type': 'ir.actions.act_window_close'}

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.activity',
            'res_id': self.accounting_activity_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
