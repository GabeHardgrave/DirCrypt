"""
cryptor

Utilities for (En|De)crypting.
"""
__all__ = ['Cryptor', 'Encryptor', 'Decryptor']

import os
import binascii
from pathlib import Path
from getpass import getpass
from typing import Optional, Tuple
from base64 import urlsafe_b64encode, urlsafe_b64decode
from abc import ABCMeta, abstractproperty, abstractmethod

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from dircrypt.ioutils import BLOCK_SIZE, force_create_file

# -----------------------------------------------------------------------------

# Security Parameters
SALT_SIZE = 16
DEFAULT_PASSWORD_SIZE = 32
KEY_STRETCH_COUNT = 100000
KEY_SIZE = 32
NONCE_SIZE = 12

# Derived Parameters
CHACHA_TAG_SIZE = 16
ENC_READ_SIZE = BLOCK_SIZE
DEC_READ_SIZE = ENC_READ_SIZE + CHACHA_TAG_SIZE + SALT_SIZE + NONCE_SIZE

# calculated ahead of time purely for efficiency; strictly used in _decrypt()
START_OF_NONCE = SALT_SIZE
END_OF_NONCE = START_OF_NONCE + NONCE_SIZE
START_OF_CIPHERTEXT = END_OF_NONCE

# -----------------------------------------------------------------------------

class Cryptor(metaclass=ABCMeta):
    """Interface for common operations over (en|de)cryption"""

    @abstractmethod
    def crypt_path_name(self, path_item_name: str) -> Optional[str]:
        """
        (En|De)crypts the given str, returning a new str suitable for a file or
        directory name. Returns `None`if decryption fails.
        """
        pass

    @abstractmethod
    def crypt_file_contents(self, data: bytes) -> Optional[bytes]:
        """
        (En|De)crypts the given byte string. Returns `None` on failed
        decryption. Meant for file contents.
        """
        pass

    @abstractproperty
    def read_len(self) -> int:
        """The largest number of bytes to read in a single IO operation"""
        pass

    @abstractproperty
    def write_len(self) -> int:
        """The largest number of bytes to write in a single IO operation."""
        pass

    @abstractproperty
    def output_dirname(self) -> str:
        """Name of the output directory"""
        pass

    @abstractproperty
    def verb(self) -> str:
        """'Encrypting' or 'Decrypting'"""
        pass

class Encryptor(Cryptor):
    """Encryption Handler"""

    def __init__(self, gen_psw: bool=False):
        """
        If `gen_psw` is set, a cryptographically secure, pseudorandom password
        is generated for encryption. Otherwise the password is queried through
        STDIN.

        Raises:
            `OSError`: If `gen_psw != None` and an IO-Error occurred.
        """
        (self._psw, psw_file) = create_psw_file() if gen_psw else (None, None)

        if psw_file is not None:
            assert(self._psw is not None)
            print("Autogenerated password saved to '{}'".format(psw_file))

        while self._psw is None:
            candidate = getpass(prompt="Password: ")
            check = getpass(prompt="Verify Password: ")
            if candidate == check:
                self._psw = bytes(check, "utf-8")
            else:
                print("Passwords to not match. Please try again.")

    def crypt_path_name(self, path_item_name: str) -> Optional[str]:
        """
        Encrypts the given str, returning a new str suitable for a file or
        directory name.
        """
        path_bytes = bytes(path_item_name, "utf-8")
        ciphertext = self._encrypt(path_bytes)
        b64_path_bytes = urlsafe_b64encode(ciphertext)
        return str(b64_path_bytes, "utf-8")

    def crypt_file_contents(self, data: bytes) -> Optional[bytes]:
        """
        Encrypts the given byte string. Meant for file contents. Assumes
        `len(data) <= Encryptor.read_len`
        """
        assert(len(data) <= self.read_len)
        return self._encrypt(data)

    @property
    def read_len(self) -> int:
        """The number of bytes to read in a single IO operation"""
        return ENC_READ_SIZE

    @property
    def write_len(self) -> int:
        """The largest number of bytes to write in a single IO operation."""
        return DEC_READ_SIZE

    @property
    def output_dirname(self) -> str:
        """Name of the output directory"""
        return "ENCRYPTED_OUTPUT"

    @property
    def verb(self) -> str:
        """'Encrypting'"""
        return "Encrypting"

    def _encrypt(self, plaintext: bytes) -> bytes:
        """Encryption"""
        salt = os.urandom(SALT_SIZE)
        nonce = os.urandom(NONCE_SIZE)
        key = derive_key(password=self._psw, salt=salt)
        cipher = ChaCha20Poly1305(key)
        ciphertext = cipher.encrypt(nonce, plaintext, None)

        # Somewhat counterintuitively, benchmarking revealed that it was faster
        # to concatenate bytes than use bytearray.extend
        return salt + nonce + ciphertext

class Decryptor(Cryptor):
    """Decryption Handler"""

    def __init__(self, psw_file: Optional[str]=None):
        """
        Initializes the key from the given user password or password file.

        Raises (if `psw_file` is not None):
            `OSError`: If some other IO related error occurred
        """
        if psw_file is None:
            psw = getpass(prompt="Password: ")
            self._psw = bytes(psw, "utf-8")
        else:
            self._psw = read_psw_file(Path(psw_file))

    def crypt_path_name(self, path_item_name: str) -> Optional[str]:
        """
        Decrypts the given str, returning a new str suitable for a file or
        directory name. Returns `None` if `path_item_name` couldn't be
        decrypted.
        """
        b64_path_bytes = bytes(path_item_name, "utf-8")
        path_bytes = None
        try:
            path_bytes = urlsafe_b64decode(b64_path_bytes)
        except binascii.Error:
            return None
        assert(path_bytes is not None)

        plaintext_bytes = self._decrypt(path_bytes)
        if plaintext_bytes is None:
            return None
        else:
            return str(plaintext_bytes, "utf-8")

    def crypt_file_contents(self, data: bytes) -> Optional[bytes]:
        """
        Decrypts the given byte string. Meant for file contents. Assumes
        `len(data) <= Decryptor.read_len`. Returns `None` if decryption fails.
        """
        assert(len(data) <= self.read_len)
        return self._decrypt(data)

    @property
    def read_len(self) -> int:
        """The number of bytes to read in a single IO operation"""
        return DEC_READ_SIZE

    @property
    def write_len(self) -> int:
        """The largest number of bytes to write in a single IO operation."""
        return ENC_READ_SIZE

    @property
    def output_dirname(self) -> str:
        """Name of the output directory"""
        return "DECRYPTED_OUTPUT"

    @property
    def verb(self) -> str:
        """'Decrypting'"""
        return "Decrypting"

    def _decrypt(self, ciphertext: bytes) -> Optional[bytes]:
        """Decryption. Returns `None` if decryption fails."""
        salt = ciphertext[0:SALT_SIZE]
        nonce = ciphertext[START_OF_NONCE:END_OF_NONCE]
        ciphertext_and_tag = ciphertext[START_OF_CIPHERTEXT:]

        is_malformed = (len(salt) != SALT_SIZE or
                        len(nonce) != NONCE_SIZE or
                        len(ciphertext_and_tag) < CHACHA_TAG_SIZE)

        if is_malformed:
            return None

        key = derive_key(password=self._psw, salt=salt)
        cipher = ChaCha20Poly1305(key)

        try:
            plaintext = cipher.decrypt(nonce, ciphertext_and_tag, None)
            return plaintext
        except InvalidTag:
            return None

# -----------------------------------------------------------------------------

def derive_key(password: bytes, salt: bytes) -> bytes:
    """
    Returns a url safe, base 64 encoded key for Fernet encryption. Key is
    derived from the given password, using PBKDF2HMAC.
    """
    assert(len(salt) == SALT_SIZE)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(),
                     length=KEY_SIZE,
                     salt=salt,
                     iterations=KEY_STRETCH_COUNT,
                     backend=default_backend())
    key = kdf.derive(password)
    return key

def create_psw_file(prefix: str="dircrypt") -> Tuple[bytes, Path]:
    # pylint: disable=invalid-sequence-index
    """
    Generates a new, url safe, base 64 encoded password, and writes it to disk.
    The generated password is returned, along with the path to the file
    containing the generated password.

    Raises:
        `OSError`: If file io goes wrong
    """
    psw = os.urandom(DEFAULT_PASSWORD_SIZE)
    b64_psw = urlsafe_b64encode(psw)

    psw_file = force_create_file(prefix, suffix=".password")
    psw_file.write_bytes(b64_psw)

    return b64_psw, psw_file

def read_psw_file(psw_file: Path) -> bytes:
    """
    Attempts to read the password from the given `psw_file`.

    Raises:
        `OSError`: If some IO related error occurred during file reading
    """
    if not psw_file.is_file():
        raise FileNotFoundError("'{}' does not exist".format(psw_file))

    psw = psw_file.read_bytes()
    return psw

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    raise Exception("Unimplemented")
