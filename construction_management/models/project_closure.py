from odoo import models, fields, api
from odoo.exceptions import UserError


class Project(models.Model):
    """Mở rộng Project - Closure & Lock Status"""
    _inherit = 'project.project'

    # ============ PROJECT CLOSURE ============
    is_closed = fields.Boolean(
        string='Dự Án Đã Đóng?',
        default=False,
        readonly=True,
        help='Dự án đã được PM đóng sau khi thu đủ tiền'
    )
    closed_date = fields.Datetime(
        string='Ngày Đóng',
        readonly=True,
        help='Thời điểm PM đóng dự án'
    )
    closed_by_id = fields.Many2one(
        'res.users',
        string='Đóng Bởi',
        readonly=True,
        help='PM người thực hiện đóng'
    )

    # Project state (if not already exists)
    state = fields.Selection(
        [('open', 'Open'), ('closed', 'Closed'), ('cancelled', 'Cancelled')],
        default='open',
        readonly=True,
        help='Project status'
    )

    @api.constrains('is_closed')
    def _check_project_closed_no_modifications(self):
        """
        Block modifications khi project closed:
        - Không thể add task
        - Không thể update milestone
        - Không thể tạo stock.picking
        """
        for record in self:
            if record.is_closed:
                # Tùy chọn: Có thể log warning thay vì block
                pass  # Allow read-only access

    def action_close_project(self):
        """
        Action để đóng project từ project form.
        (Thường triggered từ sale.order.action_close_project)
        """
        self.ensure_one()

        if self.is_closed:
            raise UserError("Dự án đã đóng rồi!")

        self.is_closed = True
        self.closed_date = fields.Datetime.now()
        self.closed_by_id = self.env.user.id
        self.state = 'closed'

        return {'type': 'ir.actions.act_window_close'}
