import importlib.util
import os
import pkgutil
from typing import List, Optional

from ..utils import import_submodules


__path__: List[str]
__path__ = [os.path.abspath(path) for path in pkgutil.extend_path(__path__, __name__)]

__all__: List[str] = []


def _bundled_converters_path() -> Optional[str]:
    """Return the location of the ``converters`` package shipped with this tool."""
    spec = importlib.util.find_spec("converters")
    if spec is not None and spec.submodule_search_locations:
        return os.path.abspath(list(spec.submodule_search_locations)[0])
    return None


def import_converters():
    global __path__, __all__
    bundled_path: Optional[str] = _bundled_converters_path()
    if bundled_path is not None and bundled_path not in __path__:
        __path__.append(bundled_path)
    __all__ = import_submodules(__path__, globals(), package=__name__)
