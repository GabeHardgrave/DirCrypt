"""
dircrypt

Usage:
    dircrypt (-e | -d) <target>
    dircrypt (--encrypt | --decrypt) <target>
    dircrypt (-e | --encrypt) <target> [--gen] [--as=<output>]
    dircrypt (-d | --decrypt) <target> [--with=<psw_file>] [--as=<output>]

Options:
    -e --encrypt    encrypt the target directory/file
    -d --decrypt    decrypt the target directory/file
    --as=<output>     name of the output directory, where (en|de)crypted
                      file(s) are stored
    --gen   use securely generated password, instead of a user generated
            password
    --with=<psw_file>   read the password from the given file, instead of STDIN
                        (useful for long, securely generated passwords)
"""
import sys
from pathlib import Path
from typing import Tuple, List
from multiprocessing import Pool, Manager

from docopt import docopt
from cryptography.exceptions import InvalidTag, UnsupportedAlgorithm

from dircrypt.cryptor import Cryptor, Encryptor, Decryptor
from dircrypt.aux import implies, bench, num_available_cpus
from dircrypt.ioutils import force_create_dir_or_exit, dir_walk
from dircrypt.routines import DirectoryBuilder, crypt_path_and_contents

# -----------------------------------------------------------------------------

def parse_args(arg_list: List[str]=sys.argv[1:]) -> Tuple[Cryptor, Path, str]:
    # pylint: disable=invalid-sequence-index
    # Not sure why pylint goofs up on this one
    """
    Parses the command line arguments, according to the given usage string.
    Returns the associated `Cryptor`, target directory/file, and output
    directory/file name, in that order. Exits on malformed args.
    """
    args = docopt(__doc__, argv=arg_list, version="dircrypt 1.0")

    assert(args["--decrypt"] ^ args["--encrypt"])
    assert(args["<target>"] is not None)
    assert(implies(args["--gen"], args["--encrypt"]))
    assert(implies(args["--with"] is not None, args["--decrypt"]))

    (mode, target, new_dir) = (None, None, None)

    try:
        target = Path(args["<target>"])
        if not (target.is_dir() or target.is_file()):
            sys.exit("'{}' must be a file or directory".format(target))
    except TypeError as e:
        sys.exit("Cannot read '{}' with '{}'".format(target, e))

    try:
        mode = Encryptor(args["--gen"]) if args["--encrypt"] else \
               Decryptor(args["--with"])
    except (OSError, InvalidTag, UnsupportedAlgorithm) as e:
        sys.exit(str(e))

    new_dir = mode.output_dirname if args["--as"] is None else args["--as"]

    assert(None not in (mode, target, new_dir))

    return (mode, target, new_dir)

# -----------------------------------------------------------------------------

def main():
    """
    1) Parses command line arguments
    2) Runs the Dircrypt protocol
    """
    mode, target, new_dir = parse_args()

    path_to_target = Path(*target.parts[:-1])

    output_dir = force_create_dir_or_exit(new_dir)

    manager = Manager()
    dir_builder = DirectoryBuilder(path_to_target, output_dir, mode, manager)

    def run_dircrypt() -> None:
        """Runs dircrypt over process pool"""
        crypting_tasks = []
        with Pool(processes=num_available_cpus()) as pool:
            # manually apply_async() to avoid chunking overhead from pool.map()
            for path_to_file in dir_walk(target):
                crypt_task = pool.apply_async(func=crypt_path_and_contents,
                                              args=(dir_builder, path_to_file))
                crypting_tasks.append(crypt_task)

            _ = [task.get() for task in crypting_tasks]

    print("{} '{}'".format(mode.verb, target))
    if __debug__:
        bench(dircrypt=run_dircrypt)
    else:
        run_dircrypt()
    print("Finished {} '{}'".format(mode.verb, target))

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
