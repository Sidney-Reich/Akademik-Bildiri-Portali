"""Passwords (bcrypt) and login tokens (signed with HMAC, no session table).

Other tasks protect an endpoint like this:

    from .auth import current_person
    def my_endpoint(person_id: int = Depends(current_person)): ...
"""
import hashlib
import hmac
import os
import secrets
import time

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SECRET = (os.environ.get("SECRET_KEY") or secrets.token_hex(32)).encode()
TOKEN_SECONDS = 8 * 60 * 60
MAX_PASSWORD_BYTES = 72  # bcrypt ignores everything after this

bearer = HTTPBearer(auto_error=False)
# compared against when the email is unknown, so both cases take equally long
_DUMMY_HASH = bcrypt.hashpw(b"dummy password", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str | None) -> bool:
    data = password.encode()
    if len(data) > MAX_PASSWORD_BYTES:
        return False
    ok = bcrypt.checkpw(data, (password_hash or _DUMMY_HASH).encode())
    return ok and password_hash is not None


def _sign(payload: str) -> str:
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()


def make_token(person_id: int) -> str:
    payload = f"{person_id}.{int(time.time()) + TOKEN_SECONDS}"
    return f"{payload}.{_sign(payload)}"


def current_person(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> int:
    """The person_id of the logged-in user, or 401."""
    if cred is not None:
        payload, _, signature = cred.credentials.rpartition(".")
        if payload and hmac.compare_digest(signature.encode(), _sign(payload).encode()):
            person_id, expires = payload.split(".")
            if int(expires) > time.time():
                return int(person_id)
    raise HTTPException(401, "Lütfen oturum açın.")
