"""Compatibility helpers for optional QGIS/PyQt dependencies.

This module exposes utility classes and functions that make it possible to
import the plugin outside of a full QGIS runtime.  The production plugin runs
inside QGIS where :mod:`qgis` and :mod:`PyQt5` are available.  Our unit tests
however execute in a minimal environment that lacks these packages.  The
helpers defined here provide small stubs so that modules can still be imported
without immediately failing.  The stubs either raise descriptive errors or
implement the tiny subset of behaviour that the tests rely on.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Dict


class MissingDependency:
    """Descriptor that raises a consistent error when accessed.

    The real QGIS/PyQt classes are only available inside a QGIS runtime.  When
    they cannot be imported we expose a :class:`MissingDependency` placeholder
    so that the failure surface is explicit.  Unit tests patch these
    placeholders with mocks, while regular code will receive a clear
    ``ModuleNotFoundError`` instead of an ``ImportError`` during module import.
    """

    def __init__(self, fq_name: str) -> None:
        self._fq_name = fq_name

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover -
        raise ModuleNotFoundError(
            f"Dependency '{self._fq_name}' is not available. Install QGIS "
            "with Python support to use this functionality."
        )

    def __getattr__(self, item: str) -> Any:  # pragma: no cover - error path
        if item.startswith("_"):
            # Support private attribute checks performed by :mod:`unittest.mock`.
            raise AttributeError(item)

        raise ModuleNotFoundError(
            f"Dependency '{self._fq_name}' (attribute '{item}') is not "
            "available. Install QGIS with Python support to use this "
            "functionality."
        )


@dataclass
class _NullExtent:
    """Very small extent object used by the ``iface`` stub."""

    def xMaximum(self) -> int:
        return 0

    def xMinimum(self) -> int:
        return 0

    def yMaximum(self) -> int:
        return 0

    def yMinimum(self) -> int:
        return 0


class _NullCanvas:
    def extent(self) -> _NullExtent:
        return _NullExtent()


class _NullSignal:
    def connect(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover -
        return None

    def disconnect(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None


class _NullMessageBar:
    def pushMessage(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None


class NullIface:
    """Light‑weight stand-in for :data:`qgis.utils.iface` used in tests."""

    layoutDesignerClosed = _NullSignal()

    def mapCanvas(self) -> _NullCanvas:
        return _NullCanvas()

    def openLayoutDesigner(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def messageBar(self) -> _NullMessageBar:
        return _NullMessageBar()


class QgsLayoutItemManualTableStub:
    """Small stub that mimics the API used in the tests."""

    @classmethod
    def create(cls, *_args: Any, **_kwargs: Any) -> "QgsLayoutItemManualTableStub":
        return cls()

    def setEmptyTableBehavior(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class QgsLayoutTableStub:
    class EmptyTableMode:
        HideTable = "HideTable"


class QgsCoordinateReferenceSystemStub:
    """Minimal representation for equality comparisons in tests."""

    def __init__(self, crs_id: Any) -> None:
        self.crs_id = crs_id

    def __eq__(self, other: object) -> bool:
        if isinstance(other, QgsCoordinateReferenceSystemStub):
            return self.crs_id == other.crs_id
        return False


class QgsLayerTreeLayerStub:
    """Trivial container used when QGIS is unavailable."""

    def __init__(self, layer: Any) -> None:
        self.layer = layer


def _load_qgis_dependencies() -> Dict[str, Any]:
    try:  # pragma: no cover - real QGIS is unavailable in tests
        from qgis.core import (
            QgsCoordinateReferenceSystem,
            QgsLayerTree,
            QgsLayerTreeGroup,
            QgsLayerTreeLayer,
            QgsLayout,
            QgsLayoutItem,
            QgsLayoutItemLegend,
            QgsLayoutItemManualTable,
            QgsLayoutItemMap,
            QgsLayoutTable,
            QgsPrintLayout,
            QgsProject,
            QgsReadWriteContext,
            QgsVectorLayer,
            Qgis,
        )
    except ModuleNotFoundError:
        return {
            "QgsCoordinateReferenceSystem": QgsCoordinateReferenceSystemStub,
            "QgsLayerTree": MissingDependency("qgis.core.QgsLayerTree"),
            "QgsLayerTreeGroup": MissingDependency("qgis.core.QgsLayerTreeGroup"),
            "QgsLayerTreeLayer": QgsLayerTreeLayerStub,
            "QgsLayout": MissingDependency("qgis.core.QgsLayout"),
            "QgsLayoutItem": MissingDependency("qgis.core.QgsLayoutItem"),
            "QgsLayoutItemLegend": MissingDependency("qgis.core.QgsLayoutItemLegend"),
            "QgsLayoutItemManualTable": QgsLayoutItemManualTableStub,
            "QgsLayoutItemMap": MissingDependency("qgis.core.QgsLayoutItemMap"),
            "QgsLayoutTable": QgsLayoutTableStub,
            "QgsPrintLayout": MissingDependency("qgis.core.QgsPrintLayout"),
            "QgsProject": MissingDependency("qgis.core.QgsProject"),
            "QgsReadWriteContext": MissingDependency("qgis.core.QgsReadWriteContext"),
            "QgsVectorLayer": MissingDependency("qgis.core.QgsVectorLayer"),
            "Qgis": SimpleNamespace(Warning="Warning", Critical="Critical"),
        }

    return {
        "QgsCoordinateReferenceSystem": QgsCoordinateReferenceSystem,
        "QgsLayerTree": QgsLayerTree,
        "QgsLayerTreeGroup": QgsLayerTreeGroup,
        "QgsLayerTreeLayer": QgsLayerTreeLayer,
        "QgsLayout": QgsLayout,
        "QgsLayoutItem": QgsLayoutItem,
        "QgsLayoutItemLegend": QgsLayoutItemLegend,
        "QgsLayoutItemManualTable": QgsLayoutItemManualTable,
        "QgsLayoutItemMap": QgsLayoutItemMap,
        "QgsLayoutTable": QgsLayoutTable,
        "QgsPrintLayout": QgsPrintLayout,
        "QgsProject": QgsProject,
        "QgsReadWriteContext": QgsReadWriteContext,
        "QgsVectorLayer": QgsVectorLayer,
        "Qgis": Qgis,
    }


def _load_pyqt_dependencies() -> Dict[str, Any]:
    try:  # pragma: no cover - PyQt5 is unavailable in tests
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtXml import QDomDocument
    except ModuleNotFoundError:
        return {
            "QApplication": MissingDependency("PyQt5.QtWidgets.QApplication"),
            "QDomDocument": MissingDependency("PyQt5.QtXml.QDomDocument"),
        }

    return {"QApplication": QApplication, "QDomDocument": QDomDocument}


def _load_iface() -> Dict[str, Any]:
    try:  # pragma: no cover - real iface is unavailable in tests
        from qgis.utils import iface
    except ModuleNotFoundError:
        return {"iface": NullIface()}

    return {"iface": iface}


def get_dependencies() -> Dict[str, Any]:
    """Return a dictionary with all exported dependency placeholders."""

    deps: Dict[str, Any] = {}
    deps.update(_load_qgis_dependencies())
    deps.update(_load_pyqt_dependencies())
    deps.update(_load_iface())
    return deps
