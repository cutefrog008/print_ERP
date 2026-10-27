"""
Off-site backup delivery by email (Gmail SMTP).

After a backup ZIP is created and verified, it is emailed to a mailbox so
a copy of the ERP data lives off the machine.

Credentials are NEVER hard-coded. They come from environment variables set
once with `setx`:
    ERP_SMTP_USER      -> the Gmail address
    ERP_SMTP_PASSWORD  -> the Gmail App Password (16 characters)

Rules:
  * One email per ZIP. A marker file '.emailed-<zipname>' records that the
    archive has been mailed, so re-runs never duplicate the same email.
  * If the ZIP is larger than the SMTP attachment limit it is NOT attached;
    a short notice email is sent instead and the log records the reason.
  * Any failure here never affects the backup itself - backup.py calls this
    only after the backup has been saved and verified.

CLI:
    python emailer.py test    -> send a small test email (no attachment)
"""

from __future__ import annotations

import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import backup as bk    # noqa: E402
import config as cfg   # noqa: E402


# =========================================================================
# Duplicate guard (one email per ZIP)
# =========================================================================

def email_marker_for(zip_path: Path) -> Path:
    return cfg.DAILY_DIR / f"{cfg.EMAIL_MARKER_PREFIX}{zip_path.name}"


def already_emailed(zip_path: Path) -> bool:
    return email_marker_for(zip_path).exists()


def mark_emailed(zip_path: Path) -> None:
    marker = email_marker_for(zip_path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        f"{bk.now_ist().isoformat()}\n{cfg.MAIL_TO}\n", encoding='utf-8')


# =========================================================================
# Message building
# =========================================================================

def _build_message(backup_path: Path, metadata: dict, attach: bool) -> EmailMessage:
    size = backup_path.stat().st_size
    meta = metadata or {}

    subject = (f"{cfg.MAIL_SUBJECT_PREFIX} - "
               f"{meta.get('backup_type', 'backup')} - "
               f"{bk.ist_date().isoformat()}")

    lines = [
        "Printing ERP - automatic backup",
        "",
        f"Backup file : {backup_path.name}",
        f"Size        : {bk.human_bytes(size)}",
        f"Type        : {meta.get('backup_type', 'backup')}",
        f"Created (IST): {bk.now_ist().strftime('%d-%m-%Y %H:%M:%S')}",
        f"Computer    : {meta.get('windows_computer_name', '')}",
        f"Database    : {bk.human_bytes(meta.get('database_size_bytes', 0))}",
        f"Django      : {meta.get('django_version', '')}",
        "",
    ]
    if attach:
        lines += [
            "The backup archive is attached to this email.",
            "Keep it as the off-site copy of the ERP database and media.",
        ]
    else:
        lines += [
            "NOTE: the archive was too large for email and is NOT attached.",
            f"It is still stored on the server at: {backup_path}",
        ]

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = cfg.SMTP_USER
    msg['To'] = cfg.MAIL_TO
    msg.set_content("\n".join(lines))

    if attach:
        msg.add_attachment(
            backup_path.read_bytes(),
            maintype='application', subtype='zip',
            filename=backup_path.name)
    return msg


# =========================================================================
# Sending
# =========================================================================

def _send(msg: EmailMessage) -> None:
    if cfg.SMTP_PORT == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg.SMTP_HOST, cfg.SMTP_PORT, context=context,
                              timeout=90) as server:
            server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
            server.send_message(msg)
    else:
        with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=90) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
            server.send_message(msg)


def send_backup_email(backup_path, metadata: dict | None = None) -> bool:
    """Email a backup ZIP to the configured mailbox. Returns True on success."""
    log = bk.get_logger()
    metadata = metadata or {}

    if not cfg.EMAIL_ENABLED:
        log.info("Email delivery disabled (ERP_EMAIL_ENABLED=0). Skipping.")
        return False
    if not cfg.SMTP_USER or not cfg.SMTP_PASSWORD:
        log.warning("Email delivery not configured "
                    "(ERP_SMTP_USER / ERP_SMTP_PASSWORD missing). Skipping.")
        return False

    backup_path = Path(backup_path)
    if not backup_path.exists():
        log.error(f"Email skipped - backup file not found: {backup_path}")
        return False
    if already_emailed(backup_path):
        log.info(f"Email already sent for {backup_path.name} - skipping duplicate.")
        return False

    size = backup_path.stat().st_size
    limit = int(cfg.EMAIL_MAX_ATTACH_MB * 1024 * 1024)
    attach = size <= limit
    if not attach:
        log.warning(
            f"Backup is {bk.human_bytes(size)}, over the "
            f"{cfg.EMAIL_MAX_ATTACH_MB:.0f} MB email limit - "
            "sending a notice WITHOUT the attachment.")

    msg = _build_message(backup_path, metadata, attach)
    try:
        log.info(f"Emailing backup to {cfg.MAIL_TO} via "
                 f"{cfg.SMTP_HOST}:{cfg.SMTP_PORT} ...")
        _send(msg)
    except Exception as e:
        log.error(f"Email delivery FAILED: {type(e).__name__}: {e}")
        return False

    mark_emailed(backup_path)
    log.info(f"[OK] Backup emailed: {backup_path.name} -> {cfg.MAIL_TO}")
    return True


# =========================================================================
# CLI
# =========================================================================

def main(argv) -> int:
    log = bk.get_logger()
    action = argv[1].lower() if len(argv) > 1 else 'test'

    if action != 'test':
        print("Usage: emailer.py test")
        return 2

    if not cfg.SMTP_USER or not cfg.SMTP_PASSWORD:
        log.error("Email not configured. Set ERP_SMTP_USER and ERP_SMTP_PASSWORD first.")
        return 1

    msg = EmailMessage()
    msg['Subject'] = f"{cfg.MAIL_SUBJECT_PREFIX} - TEST message"
    msg['From'] = cfg.SMTP_USER
    msg['To'] = cfg.MAIL_TO
    msg.set_content(
        "This is a test message from the Printing ERP backup system.\n"
        "If you received it, email backup delivery is working.\n")
    try:
        log.info(f"Sending TEST email to {cfg.MAIL_TO} via "
                 f"{cfg.SMTP_HOST}:{cfg.SMTP_PORT} ...")
        _send(msg)
    except Exception as e:
        log.error(f"Test email FAILED: {type(e).__name__}: {e}")
        return 1
    log.info(f"[OK] Test email sent to {cfg.MAIL_TO}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
