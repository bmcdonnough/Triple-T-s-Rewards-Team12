# common/second_factor.py
import secrets, string
from datetime import datetime, timedelta
from extensions import db, bcrypt
from models import Email2FACode, User
from common.logging import log_audit_event

def _random_6():
    return "".join(secrets.choice(string.digits) for _ in range(6))

def create_email_code(user: User, purpose: str, minutes=10) -> str:
    code = _random_6()
    h = bcrypt.generate_password_hash(code).decode()
    rec = Email2FACode(
        user_id=user.USER_CODE,
        purpose=purpose,
        code_hash=h,
        expires_at=datetime.utcnow() + timedelta(minutes=minutes)
    )
    db.session.add(rec)
    db.session.commit()
    return code  # return raw so caller can email it

def verify_email_code(user: User, purpose: str, code: str, max_attempts=5) -> bool:
    rec = (Email2FACode.query
           .filter_by(user_id=user.USER_CODE, purpose=purpose, consumed_at=None)
           .order_by(Email2FACode.sent_at.desc())
           .first())
    if not rec:
        return False
    if datetime.utcnow() > rec.expires_at:
        return False
    if rec.attempts >= max_attempts:
        return False
    rec.attempts += 1
    ok = bcrypt.check_password_hash(rec.code_hash, (code or "").strip())
    if ok:
        rec.consumed_at = datetime.utcnow()
    db.session.commit()
    return ok
