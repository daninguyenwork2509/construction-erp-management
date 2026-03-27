from odoo import models, fields, api
from odoo.exceptions import AccessError, UserError
from datetime import datetime


class StockPicking(models.Model):
    """Mở rộng Stock Picking - Access Control & Nghiệm Thu"""
    _inherit = 'stock.picking'

    # Link ngược về Task & PO
    task_id = fields.Many2one(
        'project.task',
        string='Project Task',
        readonly=True,
        help='Tự động điền từ PO'
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order (Báo giá)',
        readonly=True,
        compute='_compute_sale_order_id',
        store=True,
        help='Truy ngược từ task → sale.order'
    )

    # Nghiệm thu (Receiving confirmation)
    is_inspection_done = fields.Boolean(
        string='Đã Kiểm tra Chất lượng?',
        default=False,
        readonly=True
    )
    inspection_date = fields.Datetime(
        string='Ngày Kiểm tra',
        readonly=True
    )
    inspection_notes = fields.Text(
        string='Ghi chú Kiểm tra'
    )
    supervisor_id = fields.Many2one(
        'res.users',
        string='Giám sát/PM Kiểm tra',
        readonly=True,
        help='Người validate (nhận hàng)'
    )

    # Validate status
    validated_by_supervisor = fields.Boolean(
        string='Đã validate bởi Giám sát?',
        default=False,
        readonly=True
    )

    @api.depends('task_id', 'task_id.sale_order_id')
    def _compute_sale_order_id(self):
        """Lấy sale_order từ task"""
        for record in self:
            if record.task_id and record.task_id.sale_order_id:
                record.sale_order_id = record.task_id.sale_order_id
            else:
                record.sale_order_id = None

    @api.model
    def create(self, vals):
        """Khi tạo Stock Picking từ PO, auto-link task"""
        record = super().create(vals)

        # Tìm PO gốc (từ move_ids)
        if record.move_ids:
            po = record.move_ids[0].purchase_line_id.order_id

            if po and po.task_id:
                record.task_id = po.task_id

        return record

    def button_validate(self):
        """
        Override: Chỉ cho PM/Supervisor validate nhận hàng.
        Chặn Thu mua tự ký nhận khống.
        """
        self.ensure_one()

        # Kiểm tra quyền: User có thuộc nhóm "Project Manager / Site Supervisor" không?
        user = self.env.user
        pm_group = self.env.ref(
            'construction_management.group_project_manager_supervisor',
            raise_if_not_found=False
        )

        if pm_group and user not in pm_group.users:
            raise AccessError(
                f"❌ QUY ÒN TRUY CẬP BỊ TỪ CHỐI!\n\n"
                f"Chỉ có Project Manager / Site Supervisor mới được phép validate nhận hàng.\n"
                f"Người dùng hiện tại: {user.name}\n"
                f"Nhóm: {', '.join(user.groups_id.mapped('name'))}"
            )

        # Kiểm tra: Đã kiểm tra chất lượng chưa?
        if not self.is_inspection_done:
            raise UserError(
                f"⚠️ CHƯA KIỂM TRA CHẤT LƯỢNG!\n\n"
                f"Phải hoàn thành Kiểm tra Chất lượng trước khi Validate.\n"
                f"Bấm [Hoàn thành Kiểm tra] để xác nhận."
            )

        # Record supervisor info
        self.write({
            'supervisor_id': user.id,
            'validated_by_supervisor': True,
        })

        return super().button_validate()

    def action_inspection_done(self):
        """
        Hoàn thành Kiểm tra Chất lượng.
        - Mark is_inspection_done = True
        - Record inspection_date = now
        - Supervisor có thể thêm ghi chú
        """
        self.ensure_one()

        # Kiểm tra quyền: PM/Supervisor
        user = self.env.user
        pm_group = self.env.ref(
            'construction_management.group_project_manager_supervisor',
            raise_if_not_found=False
        )

        if pm_group and user not in pm_group.users:
            raise AccessError(
                "Chỉ PM/Supervisor được phép kiểm tra hàng."
            )

        if self.state not in ('assigned', 'waiting'):
            raise UserError(
                f"Trạng thái Picking phải là 'Assigned' hoặc 'Waiting' để kiểm tra.\n"
                f"Trạng thái hiện tại: {self.state}"
            )

        self.write({
            'is_inspection_done': True,
            'inspection_date': datetime.now(),
            'supervisor_id': user.id,
        })

        return {'type': 'ir.actions.act_window_close'}

    def action_open_inspection_wizard(self):
        """
        Mở form nhập ghi chú kiểm tra.
        Wizard: Chọn OK → Xác nhận is_inspection_done = True
        """
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Kiểm tra Hàng - {self.name}',
            'res_model': 'stock.picking.inspection',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_picking_id': self.id,
            }
        }


class StockPickingInspection(models.TransientModel):
    """Wizard: Nhập ghi chú kiểm tra hàng"""
    _name = 'stock.picking.inspection'
    _description = 'Stock Picking Inspection Wizard'

    picking_id = fields.Many2one(
        'stock.picking',
        required=True,
        ondelete='cascade'
    )
    inspection_notes = fields.Text(
        string='Ghi chú Kiểm tra',
        placeholder='Nhập ghi chú kiểm tra chất lượng, khối lượng, v.v.'
    )

    def action_confirm_inspection(self):
        """Xác nhận kiểm tra → Cập nhật picking"""
        self.ensure_one()

        self.picking_id.write({
            'is_inspection_done': True,
            'inspection_date': datetime.now(),
            'inspection_notes': self.inspection_notes,
            'supervisor_id': self.env.user.id,
        })

        return {
            'type': 'ir.actions.act_window_close'
        }
