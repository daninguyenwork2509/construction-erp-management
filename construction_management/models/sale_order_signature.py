from odoo import models, fields, api
from odoo.exceptions import ValidationError
import secrets
import hashlib
from datetime import datetime


class SaleOrder(models.Model):
    """Mở rộng Sale Order - Digital Signature + Portal Access"""
    _inherit = 'sale.order'

    # ============ PORTAL ACCESS & TOKEN ============
    access_token = fields.Char(
        string='Access Token',
        default=lambda self: self._generate_access_token(),
        readonly=True,
        copy=False,
        help='Token bảo mật để chia sẻ link duyệt VO qua email'
    )
    portal_url = fields.Char(
        string='Link Duyệt VO (Portal)',
        compute='_compute_portal_url',
        help='Đường link khách hàng dùng để duyệt và ký VO'
    )

    # ============ SIGNATURE & VERIFICATION ============
    is_portal_verified = fields.Boolean(
        string='Đã xác thực SĐT qua Portal?',
        default=False,
        readonly=True
    )
    verification_phone = fields.Char(
        string='SĐT xác thực',
        readonly=True,
        help='SĐT mà khách hàng dùng để xác thực trên portal'
    )
    verification_timestamp = fields.Datetime(
        string='Thời gian xác thực',
        readonly=True
    )

    # ============ DIGITAL SIGNATURE ============
    is_signed_electronically = fields.Boolean(
        string='Đã ký điện tử?',
        default=False,
        readonly=True
    )
    signed_by = fields.Char(
        string='Ký bởi (Tên)',
        readonly=True,
        help='Tên khách hàng khi ký (auto-fill = partner_id.name)'
    )
    signed_by_phone = fields.Char(
        string='Ký bởi (SĐT)',
        readonly=True,
        help='SĐT xác thực khi ký'
    )
    signature_timestamp = fields.Datetime(
        string='Thời gian ký',
        readonly=True
    )
    signature_ip = fields.Char(
        string='IP Ký',
        readonly=True,
        help='IP address của khách hàng lúc ký'
    )

    # ============ AUDIT TRAIL ============
    signature_audit_log = fields.Html(
        string='Audit Log Ký',
        readonly=True,
        compute='_compute_signature_audit_log'
    )
    portal_access_log = fields.Text(
        string='Log Truy cập Portal',
        readonly=True,
        help='Ghi vết các lần truy cập portal (IP, timestamp)'
    )

    @staticmethod
    def _generate_access_token():
        """Tạo token ngẫu nhiên 32 ký tự"""
        return secrets.token_urlsafe(32)

    @api.depends('access_token')
    def _compute_portal_url(self):
        """Tính URL portal duyệt VO"""
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url',
            default='http://localhost:8069'
        )
        for record in self:
            if record.id:
                record.portal_url = (
                    f"{base_url}/my/sale-order/{record.id}?"
                    f"access_token={record.access_token}"
                )
            else:
                record.portal_url = ''

    def action_generate_new_token(self):
        """
        Tạo lại access_token (trong trường hợp token bị lộ).
        - Xóa link cũ, tạo token mới
        """
        self.ensure_one()
        self.access_token = self._generate_access_token()
        return {'type': 'ir.actions.act_window_close'}

    def action_send_portal_link(self):
        """
        Gửi email link duyệt VO cho khách hàng.
        - Link = portal_url
        - Template: 'construction_management.email_so_portal_link'
        """
        self.ensure_one()

        if not self.partner_id.email:
            raise ValidationError(
                "Khách hàng không có email! Vui lòng nhập email trước."
            )

        # Tạo email template
        template = self.env.ref(
            'construction_management.email_so_portal_link',
            raise_if_not_found=False
        )

        if template:
            template.send_mail(self.id, force_send=True)
        else:
            # Fallback: Gửi email thủ công
            self.message_post(
                subject=f"Link duyệt VO: {self.name}",
                body=f"""
                    <p>Xin chào {self.partner_id.name},</p>
                    <p>Vui lòng truy cập link dưới đây để duyệt Báo giá:</p>
                    <p><a href="{self.portal_url}">{self.portal_url}</a></p>
                    <p>Xin cảm ơn!</p>
                """,
                email_from=self.user_id.email or 'noreply@company.vn',
                email_to=self.partner_id.email,
            )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ir.actions.act_url',
            'url': f"mailto:{self.partner_id.email}?subject=Link duyệt VO {self.name}",
        }

    def verify_portal_access(self, phone_input):
        """
        Kiểm tra SĐT + Cấp quyền truy cập portal.

        Logic:
        - Normalize phone: Loại bỏ space, dash, +84 → 0
        - So sánh với partner_id.phone hoặc partner_id.mobile
        - Nếu khớp → return True + ghi log
        - Nếu không → return False
        """
        self.ensure_one()

        # Normalize phone input
        normalized_input = self._normalize_phone(phone_input)

        # Lấy phone từ partner
        partner_phones = [
            self._normalize_phone(self.partner_id.phone or ''),
            self._normalize_phone(self.partner_id.mobile or ''),
        ]

        # Kiểm tra khớp
        is_valid = normalized_input in partner_phones and normalized_input

        if is_valid:
            # Ghi log xác thực thành công
            self._log_portal_access(
                action='VERIFIED',
                phone=normalized_input,
                ip='0.0.0.0'  # Sẽ lấy từ request.remote_addr ở controller
            )

            # Update verification info
            self.write({
                'is_portal_verified': True,
                'verification_phone': normalized_input,
                'verification_timestamp': datetime.now(),
            })

        return is_valid

    @staticmethod
    def _normalize_phone(phone_str):
        """
        Normalize phone number:
        - Loại bỏ space, dash, bracket
        - +84 → 0
        - Chỉ giữ lại số
        """
        if not phone_str:
            return ''

        # Loại bỏ ký tự không phải số
        cleaned = ''.join(c for c in str(phone_str) if c.isdigit() or c == '+')

        # +84 → 0
        if cleaned.startswith('+84'):
            cleaned = '0' + cleaned[3:]
        elif cleaned.startswith('84'):
            cleaned = '0' + cleaned[2:]

        return cleaned

    def sign_electronically(self, phone_verified, ip_address='0.0.0.0'):
        """
        Ký điện tử sau khi xác thực SĐT.
        - signed_by = partner_id.name
        - signed_by_phone = phone_verified
        - signature_timestamp = now
        - signature_ip = ip_address
        """
        self.ensure_one()

        if not self.is_portal_verified:
            raise ValidationError(
                "Chưa xác thực SĐT! Vui lòng xác thực trước khi ký."
            )

        # Cập nhật info ký
        self.write({
            'is_signed_electronically': True,
            'signed_by': self.partner_id.name,
            'signed_by_phone': phone_verified,
            'signature_timestamp': datetime.now(),
            'signature_ip': ip_address,
        })

        # Ghi log
        self._log_portal_access(
            action='SIGNED',
            phone=phone_verified,
            ip=ip_address
        )

        return True

    def _log_portal_access(self, action, phone='', ip='0.0.0.0'):
        """
        Ghi vết truy cập portal.

        Format: [2024-03-26 14:30:45] VERIFIED | SĐT: 0912345678 | IP: 192.168.1.1
        """
        log_entry = (
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{action} | SĐT: {phone} | IP: {ip}\n"
        )

        current_log = self.portal_access_log or ''
        self.write({
            'portal_access_log': current_log + log_entry
        })

    @api.depends('signed_by', 'signature_timestamp', 'signature_ip')
    def _compute_signature_audit_log(self):
        """Tạo HTML audit log để hiển thị trên form"""
        for record in self:
            if record.is_signed_electronically:
                record.signature_audit_log = f"""
                    <div style="background: #f0f0f0; padding: 10px; border-radius: 5px;">
                        <p><strong>📋 CHỮ KÝ ĐIỆN TỬ</strong></p>
                        <p><strong>Ký bởi:</strong> {record.signed_by}</p>
                        <p><strong>SĐT:</strong> {record.signed_by_phone}</p>
                        <p><strong>Thời gian:</strong> {record.signature_timestamp.strftime('%d/%m/%Y %H:%M:%S') if record.signature_timestamp else 'N/A'}</p>
                        <p><strong>IP Address:</strong> {record.signature_ip}</p>
                    </div>
                    <hr/>
                    <pre style="font-size: 11px; background: #fff; padding: 10px;">{record.portal_access_log or 'Không có log'}</pre>
                """
            else:
                record.signature_audit_log = '<p style="color: gray;">Chưa ký điện tử</p>'
