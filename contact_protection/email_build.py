"""Build plain-text + HTML contact notification emails with escaped user content."""

from __future__ import annotations

import html

from contact_protection.validation import sanitize_header_value


def build_contact_email_parts(
    *,
    sender_name: str,
    sender_email: str,
    message_body: str,
    is_press: bool,
    subject_type: str = '',
) -> tuple[str, str, str]:
    name = sanitize_header_value(sender_name) or 'Unknown'
    st = (subject_type or '').strip().lower()
    if st == 'data_issue':
        subject = 'PBJ320 Data Issue'
    elif is_press:
        subject = f'PRESS REQUEST: {name}'
    else:
        subject = f'PBJ320 Request: {name}'

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
    return subject, plain, html_body
