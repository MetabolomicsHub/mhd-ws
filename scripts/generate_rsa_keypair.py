import logging
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


def generate_rsa_keypair():
    """Generates an RSA private key and its public counterpart."""
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=4096, backend=default_backend()
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_pem, public_pem


def main():
    logger.info("Generating RS256 Keypair...")
    private_pem, public_pem = generate_rsa_keypair()
    Path(".secrets/.keys").mkdir(exist_ok=True, parents=True)
    # Save keys to files
    private_key_path = Path(".secrets/.keys/private_key.pem")
    private_key_path.write_bytes(private_pem)
    private_key_path.chmod(0o600)

    public_key_path = Path(".secrets/.keys/public_key.pem")
    public_key_path.write_bytes(public_pem)

    logger.info("Keys saved to .secrets/.keys")


if __name__ == "__main__":
    main()
