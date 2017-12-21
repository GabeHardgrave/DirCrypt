"""
aux

Misc helper utilities.
"""
__all__ = ['implies', 'starts_with', 'debug_print', 'bench',
           'num_available_cpus']

import os
from timeit import default_timer
from typing import TypeVar, Sequence, Tuple, Callable, Dict

# -----------------------------------------------------------------------------

T = TypeVar('T')
F = Callable[[], None]

# -----------------------------------------------------------------------------

def implies(cond1: bool, cond2: bool) -> bool:
    """Logical Implication, i.e. cond1 => cond2"""
    return (not cond1) or cond2

def starts_with(full: Sequence[T], sub: Sequence[T]) -> bool:
    """Whether `full` starts with `sub`"""
    if len(sub) > len(full):
        return False
    else:
        return full[:len(sub)] == sub

def debug_print(*args, **kwargs) -> None:
    """Wrapper for printing in __debug__ builds"""
    if __debug__:
        print("DEBUG :: ", *args, **kwargs)

def num_available_cpus() -> int:
    """
    Number of available cpus for current process. By default, this tries to
    use `os.sched_getaffinity`. If that is unavailable, `os.cpu_count()` is
    used instead.
    """
    try:
        my_pid = 0
        available_cpus = os.sched_getaffinity(my_pid)
        return len(available_cpus)
    except AttributeError:
        return os.cpu_count()

def bench(**jobs: Dict[T, F]) -> None:
    """Naively benchmarks the given functions."""
    for name, job in jobs.items():
        start_time = default_timer()
        job()
        total_time = default_timer() - start_time
        print("{} took {} time".format(name, total_time))

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    raise Exception("Unimplemented")
