import datetime
from pathlib import Path

import jwt

AUDIENCE = "https://www.metabolomicshub.org"


def create_jwt_token(
    sub: str, private_key_path: str, exp: None | datetime.datetime = None
) -> str:
    """
    Create a JWT token using RSA private key.

    Args:
        sub (str): Subject claim.
        private_key_path (str): Path to the RSA private key file.
        exp (datetime.datetime | None): Expiration datetime. If None, defaults to 2 years from now.

    Returns:
        str: JWT token as a string.
    """
    # Load RSA private key
    with Path(private_key_path).open("rb") as key_file:
        private_key = key_file.read()

    now = datetime.datetime.now(datetime.timezone.utc)
    if exp is None:
        exp = now + datetime.timedelta(days=365 * 2)  # Default: 2 years

    # Define the JWT payload
    payload = {
        "sub": sub,
        "aud": AUDIENCE,
        "iat": now,
        "exp": exp,
    }
    # Create the JWT token using RS256 algorithm
    token = jwt.encode(payload, private_key, algorithm="RS256")

    return token
