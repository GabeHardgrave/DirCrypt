"""
ioutils

Utilities for File IO
"""
__all__ = ['force_create_dir', 'force_create_file', 'label_malformed',
           'force_create_dir_or_exit', 'create_path_and_file', 'dir_walk',
           'parse_file_path', 'gen_malformed_name', 'BLOCK_SIZE']

import sys
from pathlib import Path
from typing import Tuple, Iterable

from dircrypt.aux import starts_with

# -----------------------------------------------------------------------------

# Maximum number of bytes to read in a single file IO read
BLOCK_SIZE = 16384 # 2**14

# -----------------------------------------------------------------------------

def dir_walk(root: Path) -> Path:
    """
    Iterator over all the files in the given directory (including sub
    directories). Only files are returned. If `root` is a file, only `root` is
    `yield`ed. Items are `yield`ed in no particular order.
    """
    if root.is_file():
        yield root
    elif root.is_dir():
        subdirs = [root]
        while len(subdirs) > 0:
            directory = subdirs.pop()
            for path_item in directory.iterdir():
                if path_item.is_dir():
                    subdirs.append(path_item)
                elif path_item.is_file():
                    yield path_item

def force_create_dir(dir_name: str) -> Path:
    """
    Creates a new directory with the given name to disk, returning the
    associated Path object. If `dir_name` already exists, an incremented number
    is appended until the new directory can be created.

    Raises:
        `OSError`: If `dir_name` cannot be created
    """
    i = 0
    i_str = ""

    while True:
        new_dir = dir_name + i_str
        try:
            dir_obj = Path(new_dir)
            dir_obj.mkdir(parents=True, exist_ok=False)
            return dir_obj
        except FileExistsError:
            i_str = str(i)
            i += 1

def force_create_dir_or_exit(dir_name: str) -> Path:
    """Wrapper over `force_create_dir`. Exits on failure."""
    output_dir = None
    try:
        output_dir = force_create_dir(dir_name)
        return output_dir
    except PermissionError as e:
        err_msg = "Lacking permission to create '{}' with '{}'"\
                                            .format(dir_name, e)
        sys.exit(err_msg)

def force_create_file(file_name: str, suffix: str="") -> Path:
    """
    Creates the new file with the given name to disk, returning the
    associated object. If the given file already exists, an incremented number
    is appended until the new file can be created.

    Raises:
        `OSError`: If file_name cannot be created.
    """
    i = 0
    i_str = ""

    while True:
        new_file = file_name + i_str + suffix
        try:
            file_obj = Path(new_file)
            file_obj.touch(exist_ok=False)
            return file_obj
        except FileExistsError:
            i_str = str(i)
            i += 1

def parse_file_path(root: Path, path: Path) -> Tuple[Iterable[str], str]:
    # pylint: disable=invalid-sequence-index
    """
    Given a base path with a corresponding root and terminal file element,
    pulls out and returns the intermediate path elements between root and the
    terminal file element.

    e.g. (root="foo/bar", path="foo/bar/biz/baz.txt") -> (["biz/"], "baz.txt")
    """
    assert(path.is_file())
    assert(starts_with(path.parts, root.parts))

    full_parts = path.relative_to(root).parts
    assert(len(full_parts) > 0)

    (intermediate, terminal_file) = (full_parts[0:-1], full_parts[-1])
    assert(path.relative_to(root) == \
           Path(*intermediate).joinpath(Path(terminal_file)))

    return (intermediate, terminal_file)

def create_path_and_file(path: Path) -> None:
    """A combination of mkdir and touch on the given path. Raises: `OSError`"""
    parts = path.parts
    dir_component = Path(*parts[:-1])
    dir_component.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=False)

def gen_malformed_name(is_dir: bool=True) -> str:
    """
    Returns a unique, freshly generated path item name marking malformed data
    """
    while True:
        try:
            name = "MALFORMED_DIR_NAME_{}" if is_dir else \
                   "MALFORMED_FILE_NAME_{}"
            unique_name = name.format(gen_malformed_name.increment)
            gen_malformed_name.increment += 1
            return unique_name
        except AttributeError:
            gen_malformed_name.increment = 0

def label_malformed(path: Path) -> Path:
    """
    Renames the file at the given location to <original_filename>_MALFORMED.
    If such a file already exists, an incremented number is appended to the
    name until it can be created. The new file name is returned.

    Raises: `OSError`
    """
    assert(path.is_file())

    malformed_file_path = list(path.parts)
    malformed_file_path[-1] += "_MALFORMED_CONTENTS"
    malformed_file = Path(*malformed_file_path)

    # Avoid naming collision
    i = 1
    while malformed_file.is_file():
        malformed_file_path[-1] += str(i)
        malformed_file = Path(*malformed_file_path)
        i += 1

    path.rename(malformed_file)
    return malformed_file

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    raise Exception("Unimplemented")
