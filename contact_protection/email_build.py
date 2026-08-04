"""Build plain-text + HTML contact notification emails with escaped user content."""

from __future__ import annotations

import html
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _safe_header_fragment(value: str) -> str:
    return re.sub(r'[\r\n]+', ' ', (value or '')).strip()[:200]


def contact_subject(*, sender_name: str, is_press: bool, subject_type: str = '') -> str:
    name = _safe_header_fragment(sender_name) or 'Unknown'
    st = (subject_type or '').strip().lower()
    if st == 'data_issue':
        return 'PBJ320 Data Issue'
    if is_press:
        return f'PRESS REQUEST: {name}'
    return f'PBJ320 Request: {name}'


def build_contact_bodies(
    *,
    sender_name: str,
    sender_email: str,
    message_body: str,
    is_press: bool,
) -> tuple[str, str]:
    media = 'Yes' if is_press else 'No'
    plain = '\n'.join(
        [
            f'Name: {sender_name}',
            f'Email: {sender_email}',
            f'Media: {media}',
            '',
            'Message:',
            message_body,
        ]
    )
    esc_name = html.escape(sender_name, quote=True)
    esc_email = html.escape(sender_email, quote=True)
    esc_media = html.escape(media, quote=True)
    esc_msg = html.escape(message_body, quote=True).replace('\n', '<br>\n')
    html_body = (
        '<!DOCTYPE html><html><body style="font-family:sans-serif;font-size:14px;color:#111;">'
        f'<p><strong>Name:</strong> {esc_name}</p>'
        f'<p><strong>Email:</strong> {esc_email}</p>'
        f'<p><strong>Media:</strong> {esc_media}</p>'
        f'<p><strong>Message:</strong></p>'
        f'<p>{esc_msg}</p>'
        '</body></html>'
    )
    return plain, html_body


def build_contact_mime(
    *,
    from_addr: str,
    to_list: list[str],
    reply_to: str,
    subject: str,
    plain: str,
    html_body: str,
) -> MIMEMultipart:
    msg = MIMEMultipart('alternative')
    msg['Subject'] = _safe_header_fragment(subject)
    msg['From'] = _safe_header_fragment(from_addr)
    msg['To'] = ', '.join(_safe_header_fragment(a) for a in to_list)
    msg['Reply-To'] = _safe_header_fragment(reply_to)
    msg.attach(MIMEText(plain, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    return msg
