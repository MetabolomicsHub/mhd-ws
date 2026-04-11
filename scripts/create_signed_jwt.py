import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dateutil.relativedelta import relativedelta

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


def create_rs256_token(
    private_pem: bytes, public_pem: bytes, payload_data: dict, delta: relativedelta
):
    """Creates a JWT signed with RS256 using the provided private PEM."""
    # Define standard payload with expiration and security claims
    now = datetime.now(timezone.utc)
    payload = {
        "iss": payload_data.get("sub"),
        "exp": now + delta,
        "nbf": now,
        "iat": now,
        "jti": str(uuid.uuid4()),
        **payload_data,
    }

    # Generate a Key ID (kid) from the public key hash
    kid = hashlib.sha256(public_pem).hexdigest()[:16]

    # Sign the payload using the private key, specifying explicit headers
    token = jwt.encode(
        payload,
        private_pem,
        algorithm="RS256",
        headers={"typ": "JWT", "alg": "RS256", "kid": kid},
    )
    return token


def create_signed_jwt(repository_name: str, delta: relativedelta):
    logger.info("Loading RS256 Keypair...")
    private_key_path = Path(".secrets/.keys/private_key.pem")
    public_key_path = Path(".secrets/.keys/public_key.pem")

    # Security check: verify private key permissions are restrictive (0o600)
    if (private_key_path.stat().st_mode & 0o777) != 0o600:
        logger.warning(
            "Security vulnerability: private_key.pem has insecure permissions! "
            "Please run 'chmod 600 %s'",
            private_key_path,
        )

    private_pem = private_key_path.read_bytes()
    public_pem = public_key_path.read_bytes()
    logger.info("Keys loaded from .secrets/.keys")

    # Define your JWT payload
    payload_data = {
        "sub": repository_name,
        "aud": "https://www.metabolomicshub.org",
    }

    logger.info("Creating Signed Token...")
    token = create_rs256_token(private_pem, public_pem, payload_data, delta)

    logger.info("%s", token)
    Path(".secrets/.keys/signed_jwt_token.txt").write_text(token)


if __name__ == "__main__":
    create_signed_jwt("MetaboLights", relativedelta(years=1))
