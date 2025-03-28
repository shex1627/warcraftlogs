warcraftlogs/utils.py

"""
Utility functions for the Warcraft Logs API client.
"""

import base64
import hashlib
import secrets
import string
from typing import Tuple

def generate_pkce_verifier_and_challenge() -> Tuple[str, str]:
    """
    Generate a PKCE code verifier and its corresponding challenge.
    
    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # Generate a random code verifier (between 43-128 chars as per RFC 7636)
    allowed_chars = string.ascii_letters + string.digits + "-._~"
    code_verifier = ''.join(secrets.choice(allowed_chars) for _ in range(128))
    
    # Generate code challenge by hashing the verifier with SHA-256
    code_challenge_digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge_digest).decode().rstrip('=')
    
    return code_verifier, code_challenge


def generate_random_state() -> str:
    """
    Generate a random state parameter for OAuth security.
    
    Returns:
        A random hex string
    """
    return secrets.token_hex(16)