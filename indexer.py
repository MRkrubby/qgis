# -*- coding: utf-8 -*-
"""Background geometry indexing helpers for SnapZen Pro."""

from dataclasses import dataclass, field
from itertools import count
from typing import Dict, Iterator, Optional, Sequence, Set, Tuple

from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsSpatialIndex,
    QgsTask,
    QgsVectorLayer,
    QgsWkbTypes,
)


PointKey = Tuple[float, float]


@dataclass
class IndexBundle:
    """Container matching feature ids with cached points."""

    point_index: Optional[QgsSpatialIndex] = None
    id_to_point: Dict[int, QgsPointXY] = field(default_factory=dict)

    @property
    def centroid_index(self) -> Optional[QgsSpatialIndex]:
        """Backwards compatibility alias used by previous releases."""

        return self.point_index

    @centroid_index.setter
    def centroid_index(self, value: Optional[QgsSpatialIndex]) -> None:
        self.point_index = value

    def clear(self) -> None:
        self.point_index = None
        self.id_to_point.clear()

    def is_empty(self) -> bool:
        return not self.id_to_point


class CentroidIndexTask(QgsTask):
    """Collects vertices/centroids from visible layers into an in-memory index."""

    completed = pyqtSignal()

    def __init__(self, iface, only_visible: bool = True):
        super().__init__("SnapZenPro: Build centroid index", QgsTask.CanCancel)
        self.iface = iface
        self.only_visible = only_visible
        self.result_bundle: IndexBundle = IndexBundle()
        self.errors: Sequence[str] = ()

    # ------------------------------------------------------------------
    # QgsTask API
    # ------------------------------------------------------------------
    def run(self) -> bool:  # type: ignore[override]
        canvas = self.iface.mapCanvas()
        visible_ids = {layer.id() for layer in canvas.layers()} if self.only_visible else None

        map_settings = canvas.mapSettings()
        target_extent = map_settings.extent() if map_settings else None
        target_crs = map_settings.destinationCrs() if map_settings else None

        generated_index = QgsSpatialIndex()
        point_lookup: Dict[int, QgsPointXY] = {}
        used_keys: Set[PointKey] = set()
        id_counter = count()
        collected_errors = []

        for layer in self._candidate_layers(visible_ids):
            if self.isCanceled():
                return False

            transformer, request = self._prepare_layer_context(layer, target_crs, target_extent)

            try:
                for feature in layer.getFeatures(request):
                    if self.isCanceled():
                        return False

                    geometry = feature.geometry()
                    if geometry is None or geometry.isEmpty():
                        continue

                    for raw_point in self._iter_points(geometry, layer):
                        map_point = self._transform_point(transformer, raw_point)
                        self._remember_point(
                            map_point,
                            used_keys,
                            id_counter,
                            generated_index,
                            point_lookup,
                        )
            except Exception as exc:  # pragma: no cover - best effort logging inside QGIS
                collected_errors.append(f"{layer.name()}: {exc}")
                continue

        if point_lookup:
            self.result_bundle.point_index = generated_index
            self.result_bundle.id_to_point = point_lookup
        else:
            self.result_bundle.clear()

        self.errors = tuple(collected_errors)
        return True

    def finished(self, _ok: bool) -> None:  # noqa: D401,ARG002 - signal relay
        self.completed.emit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _candidate_layers(self, visible_ids: Optional[Set[str]]) -> Iterator[QgsVectorLayer]:
        project = QgsProject.instance()
        for layer in project.mapLayers().values():
            candidate = self._layer_if_candidate(layer, visible_ids)
            if candidate is not None:
                yield candidate

    def _layer_if_candidate(
        self, layer, visible_ids: Optional[Set[str]]
    ) -> Optional[QgsVectorLayer]:
        if self.only_visible and visible_ids is not None and layer.id() not in visible_ids:
            return None
        if not isinstance(layer, QgsVectorLayer):
            return None
        if not layer.isValid():
            return None
        try:
            wkb_type = layer.wkbType()
        except Exception:
            return None
        if wkb_type == QgsWkbTypes.NoGeometry:
            return None
        return layer

    def _prepare_layer_context(
        self,
        layer: QgsVectorLayer,
        target_crs: Optional[QgsCoordinateReferenceSystem],
        target_extent,
    ) -> Tuple[Optional[QgsCoordinateTransform], QgsFeatureRequest]:
        transformer = None
        inverse_transform = None

        if target_crs is not None and target_crs.isValid():
            layer_crs = layer.crs()
            if layer_crs != target_crs:
                project = QgsProject.instance()
                try:
                    transformer = QgsCoordinateTransform(layer_crs, target_crs, project)
                    inverse_transform = QgsCoordinateTransform(target_crs, layer_crs, project)
                except Exception:
                    transformer = None
                    inverse_transform = None

        request = QgsFeatureRequest()
        if target_extent is not None and not target_extent.isNull():
            try:
                layer_extent = target_extent
                if inverse_transform is not None:
                    layer_extent = inverse_transform.transformBoundingBox(target_extent)
                request.setFilterRect(layer_extent)
            except Exception:
                pass

        return transformer, request

    @staticmethod
    def _transform_point(
        transformer: Optional[QgsCoordinateTransform], point: Optional[QgsPointXY]
    ) -> Optional[QgsPointXY]:
        if point is None:
            return None
        if transformer is None:
            return point
        try:
            return transformer.transform(point)
        except Exception:
            return None

    @staticmethod
    def _remember_point(
        point: Optional[QgsPointXY],
        used_keys: Set[PointKey],
        id_counter: Iterator[int],
        index: QgsSpatialIndex,
        id_lookup: Dict[int, QgsPointXY],
    ) -> None:
        if point is None:
            return

        key = CentroidIndexTask._point_key(point)
        if key in used_keys:
            return
        used_keys.add(key)

        feature = QgsFeature()
        feature_id = next(id_counter)
        feature.setId(feature_id)
        feature.setGeometry(QgsGeometry.fromPointXY(point))

        try:
            index.insertFeature(feature)
        except Exception:
            used_keys.discard(key)
            return

        id_lookup[feature_id] = point

    def _iter_points(self, geom: QgsGeometry, layer: QgsVectorLayer) -> Iterator[QgsPointXY]:
        yield from self._geometry_vertices(geom)

        geometry_type = QgsWkbTypes.geometryType(layer.wkbType())
        if geometry_type == QgsWkbTypes.PolygonGeometry:
            centroid_point = self._geometry_centroid(geom)
            if centroid_point is not None:
                yield centroid_point

    @staticmethod
    def _geometry_vertices(geom: QgsGeometry) -> Iterator[QgsPointXY]:
        try:
            for vertex in geom.vertices():
                yield QgsPointXY(vertex)
            return
        except Exception:
            pass

        for point in CentroidIndexTask._fallback_vertices(geom):
            if point is not None:
                yield point

    @staticmethod
    def _fallback_vertices(geom: QgsGeometry) -> Iterator[Optional[QgsPointXY]]:
        if geom is None or geom.isEmpty():
            return

        try:
            wkb_type = geom.wkbType()
            geom_type = QgsWkbTypes.geometryType(wkb_type)
        except Exception:
            geom_type = QgsWkbTypes.UnknownGeometry

        if geom_type == QgsWkbTypes.PointGeometry:
            yield from CentroidIndexTask._safe_points(geom.asPoint, geom.asMultiPoint)
        elif geom_type == QgsWkbTypes.LineGeometry:
            yield from CentroidIndexTask._safe_sequences(geom.asPolyline, geom.asMultiPolyline)
        elif geom_type == QgsWkbTypes.PolygonGeometry:
            yield from CentroidIndexTask._safe_sequences(geom.asPolygon, geom.asMultiPolygon)
        else:
            yield from CentroidIndexTask._safe_points(geom.asPoint, geom.asMultiPoint)

    @staticmethod
    def _safe_points(*factories) -> Iterator[Optional[QgsPointXY]]:
        for factory in factories:
            try:
                data = factory()
            except Exception:
                continue
            yield from CentroidIndexTask._walk_points(data)
            return

        return

    @staticmethod
    def _safe_sequences(*factories) -> Iterator[Optional[QgsPointXY]]:
        for factory in factories:
            try:
                data = factory()
            except Exception:
                continue
            if not data:
                continue
            yield from CentroidIndexTask._walk_points(data)
            return

        return

    @staticmethod
    def _walk_points(data) -> Iterator[Optional[QgsPointXY]]:
        if data is None:
            return
        if isinstance(data, (list, tuple)):
            for item in data:
                yield from CentroidIndexTask._walk_points(item)
        else:
            try:
                yield QgsPointXY(data)
            except Exception:
                return

    @staticmethod
    def _geometry_centroid(geom: QgsGeometry) -> Optional[QgsPointXY]:
        try:
            centroid_geom = geom.centroid()
        except Exception:
            return None
        if centroid_geom and not centroid_geom.isEmpty():
            try:
                return QgsPointXY(centroid_geom.asPoint())
            except Exception:
                return None
        return None

    @staticmethod
    def _point_key(point: QgsPointXY) -> PointKey:
        return (round(point.x(), 6), round(point.y(), 6))
