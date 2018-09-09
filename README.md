# DirCrypt
A CLI for creating encrypted copies of unix directories

## About

`dircrypt.py` is a fast, simple utility for creating encrypted and decrypted copies of Unix directories and Windows folders. This is useful if you want to safely upload files to a untrusted source, such as a public FTP server. `dircrypt.py` works on all file types and formats, and can encrypt arbitrarily large files.

Since encryption (and security more generally) is non-trivial, I make no strong claims about the security of this application. That being said, any feedback, security related or otherwise, is extremely welcome.

## Usage
The docopt usage string is as follows:
```
dircrypt

Usage:
    dircrypt (-e | -d) <target>
    dircrypt (--encrypt | --decrypt) <target>
    dircrypt (-e | --encrypt) <target> [--gen] [--as=<output>]
    dircrypt (-d | --decrypt) <target> [--with=<psw_file>] [--as=<output>]

Options:
    -e --encrypt    encrypt the target directory/file
    -d --decrypt    decrypt the target directory/file
    --as=<output>     name of the output directory, where (en|de)crypted file(s) are stored
    --gen   use securely generated password, instead of a user generated password
    --with=<psw_file>   read the password from the given file, instead of STDIN (useful for long, securely generated passwords)
```

`<target>` can be a relative or absolute path to either a file or a directory/folder.

By default, dircrypt will use a user-defined password to derive the underlying keys (en|de)cryption. `--gen` overrides this behavior, and generates a new file, `dircrypt.password`, containing the generated key.

All (en|de)crypted copies are written to an output folder, aptly titled `[ENCRYPTED|DECRYPTED]_OUTPUT`, depending on which mode you chose. `--as=<output>` overrides this behavior.

## Protocol

Files are encrypted in discreet "chunks" of at most 2^14 bytes (so that files too large to fit into memory can still be traversed). File names, directory names, subdirectory names, and file contents are all encrypted as seperate messages.

Messages are encrypted and authenticated using [ChaCha20-Poly1305](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.ChaCha20Poly1305).

For each message `m` (where `m` is either a file chunk, a file name, or a directory name):

* `s` = a randomly generated, 128 bit salt (`os.urandom(16)`, specifically)
* `k` = PBKDF2HMAC over `s` and the user supplied password, using SHA256 over 100,000 iterations
* `iv` = a randomly generated, 96 bit nonce (`os.urandom(12)`, specifically)
* `(c, t)` = `Enc(m, iv, k)`, where `Enc` is ChaCha20-Poly1305 outputing the ciphertext and tag

The final output is a concatenation of the following fields:

* `s | iv | c | t`

Decryption is then a straightforward reversal.

If decryption fails for a given file name or directory name, the output file is labeled as malformed, but dircrypt will continue to attempt to decrypt the file's contents or directory's files.

If decryption fails for a given file's *contents*, dircrypt stops decryption for that file and labels the file as malformed.
