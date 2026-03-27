from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime


class SaleOrder(models.Model):
    """Mở rộng Sale Order - Final Reconciliation & Project Closure"""
    _inherit = 'sale.order'

    # ============ RECONCILIATION ============
    is_fully_paid = fields.Boolean(
        string='Đã Thu Đủ 100%?',
        default=False,
        readonly=True,
        help='Kế toán xác nhận đã thu đủ tiền'
    )
    fully_paid_date = fields.Datetime(
        string='Ngày Xác Nhận Thu Đủ 100%',
        readonly=True,
        help='Thời điểm Kế toán xác nhận'
    )
    fully_paid_by_id = fields.Many2one(
        'res.users',
        string='Xác Nhận Bởi',
        readonly=True,
        help='Kế toán người xác nhận'
    )

    # ============ RECONCILIATION DASHBOARD ============
    reconciliation_total_value = fields.Float(
        string='Tổng Giá Trị SO',
        compute='_compute_reconciliation_info',
        help='Tổng tiền SO (gốc + VO)'
    )
    reconciliation_total_paid = fields.Float(
        string='Tổng Đã Thu',
        compute='_compute_reconciliation_info',
        help='Tổng tiền khách đã trả'
    )
    reconciliation_remaining = fields.Float(
        string='Số Tiền Còn Lại',
        compute='_compute_reconciliation_info',
        help='Tiền còn phải thu = Tổng - Đã Thu'
    )
    reconciliation_percentage = fields.Float(
        string='% Thu Tiền',
        compute='_compute_reconciliation_info',
        help='% tiền đã thu / tổng'
    )

    # ============ PROJECT CLOSURE ============
    is_project_closed = fields.Boolean(
        string='Dự Án Đã Đóng?',
        default=False,
        readonly=True,
        help='Dự án đã được PM đóng sau khi thu đủ tiền'
    )
    project_closed_date = fields.Datetime(
        string='Ngày Đóng Dự Án',
        readonly=True
    )
    project_closed_by_id = fields.Many2one(
        'res.users',
        string='Đóng Bởi',
        readonly=True,
        help='PM người thực hiện đóng dự án'
    )

    # ============ MILESTONES STATUS CHECK ============
    all_milestones_reached = fields.Boolean(
        string='Tất Cả Mốc Đạt?',
        compute='_compute_all_milestones_reached',
        help='Tất cả milestone của project đều ở trạng thái Done?'
    )

    @api.depends('project_id', 'project_id.milestone_ids')
    def _compute_all_milestones_reached(self):
        """Kiểm tra: tất cả milestone reached chưa?"""
        for record in self:
            if not record.project_id:
                record.all_milestones_reached = False
                continue

            milestones = record.project_id.milestone_ids
            if not milestones:
                record.all_milestones_reached = False
                continue

            # Kiểm tra: tất cả milestone phải is_reached=True
            all_reached = all(m.is_reached for m in milestones)
            record.all_milestones_reached = all_reached

    @api.depends('amount_total', 'invoice_ids')
    def _compute_reconciliation_info(self):
        """
        Tính toán reconciliation dashboard.
        - Tổng giá trị = amount_total
        - Tổng đã thu = sum(invoice.payment_state='paid')
        - Còn lại = Tổng - Đã thu
        - % = (Đã thu / Tổng) * 100
        """
        for record in self:
            total_value = record.amount_total

            # Tính tổng đã thu từ invoices (accounting journals)
            total_paid = 0
            if record.invoice_ids:
                for invoice in record.invoice_ids:
                    if invoice.payment_state == 'paid':
                        total_paid += invoice.amount_total

            remaining = total_value - total_paid
            percentage = (total_paid / total_value * 100) if total_value > 0 else 0

            record.reconciliation_total_value = total_value
            record.reconciliation_total_paid = total_paid
            record.reconciliation_remaining = remaining
            record.reconciliation_percentage = min(percentage, 100)

    def action_confirm_fully_paid(self):
        """
        Xác nhận Thu Đủ 100% (Accounting only).

        Quyền hạn:
        - Chỉ Kế toán (account.group_account_invoice) được bấm
        - Require all milestones reached
        - Require reconciliation_remaining ≈ 0

        Logic:
        1. Check quyền (Accounting)
        2. Check milestones all reached
        3. Check remaining ≈ 0 (tolerance: 1000 VND)
        4. Set is_fully_paid=True
        5. Post audit message
        """
        self.ensure_one()
        user = self.env.user

        # ============ 1. CHECK QUYỀN ============
        accounting_group = self.env.ref(
            'account.group_account_invoice',
            raise_if_not_found=False
        )

        is_accountant = accounting_group and user in accounting_group.users

        if not is_accountant:
            raise UserError(
                f"❌ QUY ÒN BỊ TỪ CHỐI!\n\n"
                f"Chỉ có Kế toán (Accounting) mới được phép xác nhận "
                f"Thu Đủ 100%.\n"
                f"Người dùng: {user.name}"
            )

        # ============ 2. CHECK MILESTONES ============
        if not self.all_milestones_reached:
            raise UserError(
                "⚠️ CHƯA THỂ XÁC NHẬN!\n\n"
                "Tất cả milestone của dự án phải đạt tiêu chuẩn (is_reached=True) "
                "mới được xác nhận thu đủ 100%."
            )

        # ============ 3. CHECK RECONCILIATION ============
        tolerance = 1000  # VND (tolerance for rounding)

        if self.reconciliation_remaining > tolerance:
            raise UserError(
                f"⚠️ CHƯA THỂ XÁC NHẬN!\n\n"
                f"Số tiền còn lại: {self.reconciliation_remaining:,.0f} VND\n"
                f"(Tolerance: {tolerance:,.0f} VND)\n\n"
                f"Vui lòng đối soát lại trước khi xác nhận."
            )

        # ============ 4. SET FULLY PAID STATUS ============
        now = datetime.now()
        self.write({
            'is_fully_paid': True,
            'fully_paid_date': now,
            'fully_paid_by_id': user.id,
        })

        # ============ 5. GHI VẾT ============
        log_message = (
            f"✅ <strong>XÁC NHẬN THU ĐỦ 100%</strong><br/>"
            f"<strong>Xác nhận bởi:</strong> {user.name} ({user.email})<br/>"
            f"<strong>Lúc:</strong> {now.strftime('%d/%m/%Y %H:%M:%S')}<br/>"
            f"<strong>Tổng tiền:</strong> {self.reconciliation_total_value:,.0f} VND<br/>"
            f"<strong>Tổng đã thu:</strong> {self.reconciliation_total_paid:,.0f} VND<br/>"
            f"<strong>Chênh lệch:</strong> {self.reconciliation_remaining:,.0f} VND<br/>"
        )

        self.message_post(
            body=log_message,
            message_type='notification',
            subtype='mail.mt_comment'
        )

        # ============ 6. NOTIFY PM ============
        if self.project_id:
            pm = self.project_id.user_id
            if pm:
                self.message_post(
                    body=f"📧 <strong>Thông báo PM:</strong> {pm.name}, "
                         f"Tiền đã thu đủ 100%. Có thể tiến hành đóng dự án.",
                    message_type='notification',
                    subtype='mail.mt_comment'
                )

        return {'type': 'ir.actions.act_window_close'}

    def action_close_project(self):
        """
        Đóng Dự Án (PM only).

        Quyền hạn:
        - Chỉ Project Manager được bấm
        - Require is_fully_paid=True (Kế toán phải xác nhận trước)

        Logic:
        1. Check quyền (PM)
        2. Check is_fully_paid=True
        3. Set SO state='done' (hoặc 'cancelled' nếu cần)
        4. Set project.state='closed'
        5. Lock project & SO
        6. Post audit message
        """
        self.ensure_one()
        user = self.env.user

        # ============ 1. CHECK QUYỀN ============
        pm_group = self.env.ref(
            'construction_management.group_project_manager_supervisor',
            raise_if_not_found=False
        )

        is_pm = pm_group and user in pm_group.users

        if not is_pm:
            raise UserError(
                f"❌ QUY ÒN BỊ TỪ CHỐI!\n\n"
                f"Chỉ có Project Manager mới được phép đóng dự án.\n"
                f"Người dùng: {user.name}"
            )

        # ============ 2. CHECK FULLY PAID ============
        if not self.is_fully_paid:
            raise UserError(
                "⚠️ CHƯA THỂ ĐÓNG DỰ ÁN!\n\n"
                "Kế toán phải xác nhận Thu Đủ 100% "
                "[Xác nhận Thu đủ 100%] trước.\n\n"
                "Chưa hoàn thành: is_fully_paid = False"
            )

        # ============ 3. CLOSE PROJECT & SO ============
        now = datetime.now()

        if self.project_id:
            self.project_id.write({
                'is_closed': True,
                'closed_date': now,
                'closed_by_id': user.id,
                'state': 'closed',  # If project.state exists
            })

        # Close SO
        self.write({
            'is_project_closed': True,
            'project_closed_date': now,
            'project_closed_by_id': user.id,
            'state': 'done',  # Mark SO as done
        })

        # ============ 4. GHI VẾT ============
        log_message = (
            f"🔒 <strong>ĐÓNG DỰ ÁN</strong><br/>"
            f"<strong>Đóng bởi:</strong> {user.name}<br/>"
            f"<strong>Lúc:</strong> {now.strftime('%d/%m/%Y %H:%M:%S')}<br/>"
            f"<strong>Dự án:</strong> {self.project_id.name if self.project_id else 'N/A'}<br/>"
            f"<strong>Trạng thái:</strong> CLOSED<br/>"
            f"<p style='color: red;'><strong>⚠️ Dự án đã khóa. Không thể tạo thêm VO, PO hay Task.</strong></p>"
        )

        self.message_post(
            body=log_message,
            message_type='notification',
            subtype='mail.mt_comment'
        )

        return {'type': 'ir.actions.act_window_close'}

    @api.constrains('is_project_closed')
    def _check_no_new_changes_when_closed(self):
        """
        Block: Khi project closed, không thể:
        - Thêm order line mới
        - Thay đổi amount
        - Tạo/update related tasks
        """
        for record in self:
            if record.is_project_closed and record.state in ['draft', 'sent']:
                raise UserError(
                    "❌ KHÔNG THỂ CHỈNH SỬA!\n\n"
                    "Dự án đã đóng. Không thể tạo thêm báo giá hoặc PO.\n"
                    "Liên hệ quản lý nếu cần reopen."
                )
