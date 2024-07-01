from typing import Tuple, Union

__version_info__: Tuple[Union[int, str], ...] = (0, 27, 1)
__version__: str = "".join([".{}".format(str(n)) if type(n) is int else str(n) for n in __version_info__]).replace(
    ".", "", 1 if type(__version_info__[0]) is int else 0
)
__build_time__ = "2024-07-01T11:14:11.019120Z"

if __name__ == "__main__":
    print(__version__)
