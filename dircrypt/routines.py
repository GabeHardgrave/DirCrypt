"""
routines

Higher level routines for dircrypt
"""
__all__ = ['DirectoryBuilder', 'crypt_path_and_contents']

from pathlib import Path, PurePath
from multiprocessing.managers import SyncManager

from dircrypt.aux import debug_print
from dircrypt.cryptor import Cryptor
from dircrypt.ioutils import (parse_file_path, gen_malformed_name,
                              create_path_and_file, label_malformed)

# -----------------------------------------------------------------------------

class DirectoryBuilder(object):
    """
    Logic for building (en|de)crypted directories, without performing duplicate
    computations or overwriting existing data.
    """

    def __init__(
            self,
            root: Path,
            output_dir: Path,
            mode: Cryptor,
            manager: SyncManager
        ):
        """
        `root`: The path to the target directory (not including the target)
        `output_dir`: The path to the output directory
        `mode`: Encryptor or Decryptor object
        `manager`: used to generate shared dictionary and lock for building
                   directory
        """
        self._mode = mode
        self._path_to_target = root
        self._output_dir = output_dir
        self._visited_dirs = manager.dict() # Dict[Path, str]
        self._lock = manager.Lock() # since `_visited_dirs` is the only mutated
                                    # variable, locking only needs to happen
                                    # around that

    def build_file_path(self, path: Path) -> Path:
        """
        Given the original path to a target file, returns the new path to the
        output file. Path items that cannot be decrypted are labeled as
        malformed in the returned path.
        """
        intermediate_path, target_file = parse_file_path(self._path_to_target,
                                                         path)
        crypted_path = [self._output_dir]
        path_id = PurePath() # Used in distinguishing subdirs w/same name

        for path_item in intermediate_path:
            path_id = path_id.joinpath(Path(path_item))
            new_dir = None
            with self._lock:
                new_dir = self._visited_dirs.get(path_id, None)
                if new_dir is None:
                    new_dir = self._mode.crypt_path_name(path_item)
                    if new_dir is None:
                        new_dir = gen_malformed_name(is_dir=True)
                    self._visited_dirs[path_id] = new_dir

            assert(new_dir is not None)
            crypted_path.append(new_dir)

        crypted_file_name = self._mode.crypt_path_name(target_file)

        if crypted_file_name is None:
            crypted_file_name = gen_malformed_name(is_dir=False)

        crypted_path.append(crypted_file_name)
        return Path(*crypted_path)

    def write_crypted_contents(self, original: Path, target: Path) -> bool:
        """
        Writes the (en|de)crypted contents from `original` to `target`. Returns
        `True` on success, `False` on failed decryption.

        Raises:
            `OSError`: if file io goes wrong.
        """
        assert(original.is_file())
        assert(target.is_file())

        with original.open(mode="rb", buffering=self._mode.read_len) as orig, \
             target.open(mode="wb", buffering=self._mode.write_len) as targ:

            contents = orig.read(self._mode.read_len)

            while contents not in (b'', None):
                crypted_contents = self._mode.crypt_file_contents(contents)
                if crypted_contents is None:
                    return False
                check = targ.write(crypted_contents)
                assert(check == len(crypted_contents))
                contents = orig.read(self._mode.read_len)

        return True

# -----------------------------------------------------------------------------

def crypt_path_and_contents(builder: DirectoryBuilder, original: Path) -> None:
    """
    Encrypts the `target`'s path, filename, and contents according to the data
    in `builder`. `OSError`'s are logged to the end user, but otherwise
    swallowed.
    """
    assert(original.is_file())
    crypted_file = builder.build_file_path(original)

    try:
        create_path_and_file(crypted_file)
        success = builder.write_crypted_contents(original, crypted_file)
        if not success:
            malformed_file = label_malformed(crypted_file)
            print("Decrypting '{}' contents failed. "\
                    "View '{}' at your own risk."\
                    .format(original, malformed_file))

        debug_print("{} -> {}".format(original, crypted_file))

    except OSError as e:
        err_msg = "Error handling '{}'. Failed with '{}'".format(original, e)
        print(err_msg)

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    raise Exception("Unimplemented")
