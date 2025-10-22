"""Helper utilities and compatibility shims for the :mod:`printomgeving` package.

The actual print logic depends heavily on QGIS and PyQt.  These libraries are
not available in the unit test environment used for the kata.  To keep the
module importable we expose light-weight placeholders that either raise a clear
``ModuleNotFoundError`` when accessed or mimic the tiny subset of behaviour that
our tests expect.  When the plugin is executed inside QGIS the real classes are
imported instead.
"""

from __future__ import annotations

import sys
import builtins

from ._compat import get_dependencies

_DEPENDENCIES = get_dependencies()
globals().update(_DEPENDENCIES)


def _missing_helper(name: str):  # pragma: no cover - exercised when QGIS missing
    def _raiser(*_args, **_kwargs):
        raise ModuleNotFoundError(
            f"Helper '{name}' requires the full QGIS runtime to be available."
        )

    return _raiser


try:
    from .hulpfuncties import (
        get_common_fields,
        get_layout_path,
        get_onderdeel_info,
        type_checks,
    )
except ModuleNotFoundError:
    get_common_fields = _missing_helper("get_common_fields")
    get_layout_path = _missing_helper("get_layout_path")
    get_onderdeel_info = _missing_helper("get_onderdeel_info")
    type_checks = _missing_helper("type_checks")

# ``tests/test_printomgeving.py`` patches objects on a top-level ``printomgeving``
# module.  Within the plugin the real module lives at ``qgis.printomgeving``.
# Register an alias so both import styles resolve to the same module.
sys.modules.setdefault("printomgeving", sys.modules[__name__])
globals().setdefault("open", builtins.open)

__all__ = tuple(
    sorted(
        {
            *_DEPENDENCIES.keys(),
            "get_common_fields",
            "get_layout_path",
            "get_onderdeel_info",
            "type_checks",
        }
    )
)
