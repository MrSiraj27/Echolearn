import logging

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.RESEND_API_KEY

FROM_ADDRESS = "EchoLearn <onboarding@resend.dev>"


def _wrap_email(title: str, body_html: str) -> str:
    return f"""
    <div style="font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
                max-width: 480px; margin: 0 auto; padding: 32px 24px; color: #1a1a1a;">
      <h1 style="font-size: 20px; font-weight: 700; margin-bottom: 4px;">EchoLearn</h1>
      <p style="color: #6b7280; font-size: 13px; margin-top: 0;">Document-only AI chat</p>
      <div style="height: 1px; background: #e5e7eb; margin: 20px 0;"></div>
      <h2 style="font-size: 16px; margin-bottom: 12px;">{title}</h2>
      {body_html}
      <div style="height: 1px; background: #e5e7eb; margin: 24px 0;"></div>
      <p style="color: #9ca3af; font-size: 12px;">
        If you didn't request this, you can safely ignore this email.
      </p>
    </div>
    """


def _button(href: str, label: str) -> str:
    return f"""
    <a href="{href}" style="display:inline-block;background:#111827;color:#ffffff;
       padding:10px 20px;border-radius:8px;text-decoration:none;font-size:14px;
       font-weight:600;margin:12px 0;">{label}</a>
    """


def send_verification_email(to_email: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    html = _wrap_email(
        "Confirm your email",
        f"""
        <p style="font-size:14px;line-height:1.5;">
          Thanks for signing up for EchoLearn. Click below to verify your email
          address and activate your account.
        </p>
        {_button(link, "Verify email")}
        <p style="font-size:12px;color:#6b7280;">This link expires in 24 hours.</p>
        """,
    )
    _send(to_email, "Verify your EchoLearn email", html)


def send_password_reset_email(to_email: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    html = _wrap_email(
        "Reset your password",
        f"""
        <p style="font-size:14px;line-height:1.5;">
          We received a request to reset your EchoLearn password. Click below to
          choose a new one.
        </p>
        {_button(link, "Reset password")}
        <p style="font-size:12px;color:#6b7280;">This link expires in 15 minutes.</p>
        """,
    )
    _send(to_email, "Reset your EchoLearn password", html)


def _send(to_email: str, subject: str, html: str) -> None:
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping email send to %s: %s", to_email, subject)
        return
    try:
        resend.Emails.send(
            {
                "from": FROM_ADDRESS,
                "to": [to_email],
                "subject": subject,
                "html": html,
            }
        )
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
