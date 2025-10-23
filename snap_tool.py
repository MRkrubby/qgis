# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsSnappingConfig, QgsTolerance, QgsSnappingUtils
from qgis.gui import QgsMapTool, QgsVertexMarker

class SnapZenProTool(QgsMapTool):
    def __init__(self, iface, settings, index_bundle):
        super().__init__(iface.mapCanvas())
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.settings = settings
        self._index_bundle = index_bundle
        self.marker = QgsVertexMarker(self.canvas)
        self.marker.setIconType(QgsVertexMarker.ICON_CROSS)
        self.marker.setIconSize(12)
        self.marker.setPenWidth(2)
        self.marker.setColor(QColor(0, 200, 255, 230))

        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._do_snap)

        self._last_pos = None
        self._snapper = None
        self._configure_local_snapping()

    def _use_fallback(self):
        if not self.settings:
            return False
        return self.settings.get("use_fallback_index", self.settings.get("snap_centroids", False))

    def set_index_bundle(self, bundle):
        self._index_bundle = bundle

    def _configure_local_snapping(self):
        # Build a local snapping config (no base_cfg, avoids UnboundLocalError)
        local = QgsSnappingConfig()
        local.setEnabled(True)
        local.setMode(QgsSnappingConfig.AllLayers)

        t_vert = self.settings.get("snap_vertices", True)
        t_segm = self.settings.get("snap_segments", True)
        if t_vert and t_segm:
            local.setType(QgsSnappingConfig.VertexAndSegment)
        elif t_vert:
            local.setType(QgsSnappingConfig.Vertex)
        elif t_segm:
            local.setType(QgsSnappingConfig.Segment)
        else:
            local.setType(QgsSnappingConfig.Vertex)

        tol = float(self.settings.get("tolerance_value", 12.0))
        if self.settings.get("tolerance_units", "px") == "px":
            local.setUnits(QgsTolerance.Pixels)
        else:
            local.setUnits(QgsTolerance.MapUnits)
        local.setTolerance(tol)
        self._snap_cfg = local

        # Prefer canvas snapping utils; otherwise own one
        try:
            su = getattr(self.canvas, "snappingUtils", None)
            self._snapper = su() if callable(su) else QgsSnappingUtils(self.canvas)
        except Exception:
            self._snapper = QgsSnappingUtils(self.canvas)

        if hasattr(self._snapper, "setConfig"):
            try:
                self._snapper.setConfig(local)
            except Exception:
                pass

    def canvasMoveEvent(self, e):
        self._last_pos = e.pos()
        try:
            delay_ms = int(self.settings.get("debounce_ms", 10))
        except Exception:
            delay_ms = 10
        self._debounce_timer.start(max(0, delay_ms))

    def _do_snap(self):
        if self._last_pos is None:
            return
        map_pt = self.toMapCoordinates(self._last_pos)

        # Primary: C++ engine via snapping utils
        try:
            match = self._snapper.snapToMap(map_pt, self._snap_cfg)
            if match.isValid():
                self._show_marker(match.point())
                return
        except Exception:
            pass

        # Fallback: cached point index built in Python
        bundle_index = None
        if self._index_bundle:
            bundle_index = (
                getattr(self._index_bundle, "point_index", None)
                or getattr(self._index_bundle, "centroid_index", None)
            )

        if self._use_fallback() and bundle_index:
            idx = bundle_index
            ids = idx.nearestNeighbor(map_pt, 1)
            if ids:
                mu_tol = self._mu_tolerance()
                candidate = self._index_bundle.id_to_point.get(ids[0], None)
                if candidate and (candidate.sqrDist(map_pt) <= mu_tol*mu_tol):
                    self._show_marker(candidate)
                    return

        self.marker.hide()

    def _mu_tolerance(self):
        if self.settings.get("tolerance_units","px") == "px":
            return float(self.settings.get("tolerance_value",12.0)) * self.canvas.mapUnitsPerPixel()
        return float(self.settings.get("tolerance_value",12.0))

    def _show_marker(self, qpt):
        self.marker.setCenter(qpt)
        self.marker.show()

    def activate(self): self.marker.show()
    def deactivate(self): self.marker.hide()
    def isZoomTool(self): return False
    def isTransient(self): return True
    def isEditTool(self): return False
