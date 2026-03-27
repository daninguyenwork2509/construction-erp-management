from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime


class PurchaseOrder(models.Model):
    """Mở rộng Purchase Order - Cost Guardrail + Task Link"""
    _inherit = 'purchase.order'

    # Link ngược về Task & Sale Order
    task_id = fields.Many2one(
        'project.task',
        string='Project Task',
        help='Task xây dựng cần mua hàng'
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order (Báo giá)',
        compute='_compute_sale_order_id',
        store=True,
        readonly=True,
        help='Tìm từ origin hoặc task_id'
    )

    # Stop Loss tracking
    is_cost_guardrail_warning = fields.Boolean(
        string='Cảnh báo Stop Loss?',
        default=False,
        readonly=True
    )
    cost_guardrail_message = fields.Text(
        string='Thông báo Stop Loss',
        readonly=True
    )

    # Sản phẩm type: consu hoặc service
    bypass_inventory = fields.Boolean(
        string='Bỏ qua Kho (Consu/Service)?',
        default=True,
        help='Tất cả sản phẩm mua sẽ là Tiêu hao (consu) hoặc Dịch vụ (service)'
    )

    @api.depends('origin', 'task_id')
    def _compute_sale_order_id(self):
        """Tìm Sale Order từ origin (SO number) hoặc task_id"""
        for record in self:
            sale_order = None

            # Cách 1: Từ task_id
            if record.task_id and record.task_id.sale_order_id:
                sale_order = record.task_id.sale_order_id

            # Cách 2: Từ origin (trích SO name)
            elif record.origin:
                try:
                    sale_order = self.env['sale.order'].search([
                        ('name', 'ilike', record.origin)
                    ], limit=1)
                except:
                    pass

            record.sale_order_id = sale_order

    def button_confirm(self):
        """
        Override: Kiểm tra Stop Loss TRƯỚC khi confirm PO.
        - Tính tổng chi phí PO vs Tổng Giá vốn BOQ
        - Chặn nếu vượt quá (raise UserError)
        """
        for record in self:
            record._check_cost_guardrail()

        return super().button_confirm()

    def _check_cost_guardrail(self):
        """
        Kiểm tra Stop Loss:
        Tổng PO amount_untaxed (tất cả confirmed) > Tổng purchase_price SO lines?
        """
        self.ensure_one()

        if not self.sale_order_id:
            # Không tìm được SO → Warning nhưng vẫn cho confirm
            self.is_cost_guardrail_warning = True
            self.cost_guardrail_message = "⚠️ Không tìm thấy Sale Order gốc. Kiểm tra 'origin' hoặc link 'Task'."
            return

        # Lấy tất cả PO confirmed + PO hiện tại (self)
        related_pos = self.env['purchase.order'].search([
            ('state', 'in', ['purchase', 'done']),
            ('sale_order_id', '=', self.sale_order_id.id),
        ])
        related_pos |= self

        # Tính tổng chi phí PO
        total_po_cost = sum(po.amount_untaxed for po in related_pos)

        # Lấy tất cả SO Line liên quan (job_id không null)
        so_lines_with_job = self.sale_order_id.order_line_ids.filtered(
            lambda l: l.job_id
        )

        if not so_lines_with_job:
            self.is_cost_guardrail_warning = True
            self.cost_guardrail_message = "⚠️ Sale Order không có dòng BOQ nào (job_id). Kiểm tra lại báo giá."
            return

        # Tính tổng Giá vốn (Purchase Price)
        total_purchase_price = sum(
            l.purchase_price * l.product_qty if l.purchase_price else 0
            for l in so_lines_with_job
        )

        # Kiểm tra Stop Loss
        if total_po_cost > total_purchase_price:
            overbudget = total_po_cost - total_purchase_price

            self.is_cost_guardrail_warning = True
            self.cost_guardrail_message = (
                f"🚨 CẢNH BÁO STOP LOSS:\n"
                f"Tổng chi phí mua hàng: {total_po_cost:,.0f} VND\n"
                f"Giá vốn quy định (BOQ): {total_purchase_price:,.0f} VND\n"
                f"VƯỢT QUÁ: {overbudget:,.0f} VND\n\n"
                f"⚠️ Yêu cầu Giám đốc Dự án (PM) phê duyệt phát sinh trước khi xác nhận PO này!"
            )

            raise UserError(
                f"❌ DỪNG CONFIRM: Chi phí mua hàng vượt quá Giá vốn dự kiến!\n\n"
                f"{self.cost_guardrail_message}"
            )
        else:
            self.is_cost_guardrail_warning = False
            self.cost_guardrail_message = (
                f"✅ OK: Chi phí PO ({total_po_cost:,.0f}) ≤ "
                f"Giá vốn ({total_purchase_price:,.0f})"
            )

    def action_view_cost_guardrail(self):
        """
        Smart button: Xem chi tiết Stop Loss check.
        - Hiện tổng PO cost vs SO purchase_price
        - Danh sách các PO liên quan
        """
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Chi tiết Stop Loss',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }


class PurchaseOrderLine(models.Model):
    """Mở rộng Purchase Order Line - Auto set sản phẩm type"""
    _inherit = 'purchase.order.line'

    def _create_or_update_product(self, name, product_qty, product_uom, price_unit):
        """
        Khi tạo product mới từ PO line, bắt buộc set type='consu' hoặc 'service'.
        """
        product_vals = {
            'name': name,
            'uom_id': product_uom.id,
            'uom_po_id': product_uom.id,
            'type': 'consu',  # ← BẮCTẮC: Luôn set là Tiêu hao
            'list_price': price_unit,
        }
        return self.env['product.product'].create(product_vals)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """
        Kiểm tra: Nếu product type = 'product' (Lưu kho) → Warning.
        Khuyến nghị dùng 'consu' hoặc 'service' thay vì.
        """
        result = super()._onchange_product_id()

        if self.product_id and self.product_id.type == 'product':
            # Warning: Sản phẩm này là "Lưu kho" (product)
            # Nên dùng consu hoặc service cho dự án thi công
            return {
                'warning': {
                    'title': '⚠️ Cảnh báo loại sản phẩm',
                    'message': (
                        f"Sản phẩm '{self.product_id.name}' là loại 'Lưu kho' (product).\n"
                        f"Cho dự án thi công, khuyến nghị dùng 'Tiêu hao' (consu) "
                        f"hoặc 'Dịch vụ' (service) để không ảnh hưởng kho.\n\n"
                        f"Loại hiện tại: {self.product_id.type}"
                    )
                }
            }

        return result
