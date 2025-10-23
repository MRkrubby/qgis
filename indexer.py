# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import (
    QgsTask,
    QgsProject,
    QgsWkbTypes,
    QgsSpatialIndex,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsFeatureRequest,
    QgsVectorLayer,
    QgsCoordinateTransform,
)


class IndexBundle:
    def __init__(self):
        self.point_index = None
        self.id_to_point = {}

    @property
    def centroid_index(self):  # backwards compatibility for existing tool logic
        return self.point_index

    @centroid_index.setter
    def centroid_index(self, value):
        self.point_index = value


class CentroidIndexTask(QgsTask):
    completed = pyqtSignal()

    def __init__(self, iface, only_visible=True):
        super().__init__("SnapZenPro: Build centroid index", QgsTask.CanCancel)
        self.iface = iface
        self.only_visible = only_visible
        self.result_bundle = None

    def run(self):
        canvas = self.iface.mapCanvas()
        vis_ids = {layer.id() for layer in canvas.layers()} if self.only_visible else None
        map_settings = canvas.mapSettings()
        target_extent = map_settings.extent() if map_settings else None
        target_crs = map_settings.destinationCrs() if map_settings else None

        id_to_point = {}
        idx = QgsSpatialIndex()
        running_id = 0
        seen_coords = set()

        def add_point(pt_xy):
            nonlocal running_id
            if pt_xy is None:
                return
            key = (round(pt_xy.x(), 6), round(pt_xy.y(), 6))
            if key in seen_coords:
                return
            seen_coords.add(key)

            feature = QgsFeature()
            feature.setId(running_id)
            feature.setGeometry(QgsGeometry.fromPointXY(pt_xy))
            idx.insertFeature(feature)
            id_to_point[running_id] = pt_xy
            running_id += 1

        for layer in self._candidate_layers(vis_ids):
            if self.isCanceled():
                return False

            transformer, request = self._prepare_layer_context(layer, target_crs, target_extent)

            try:
                for feature in layer.getFeatures(request):
                    if self.isCanceled():
                        return False

                    geom = feature.geometry()
                    if not geom or geom.isEmpty():
                        continue

                    for pt in self._geometry_vertices(geom):
                        add_point(self._transform_point(transformer, pt))

                    if QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.PolygonGeometry:
                        centroid_point = self._geometry_centroid(geom)
                        if centroid_point is not None:
                            add_point(self._transform_point(transformer, centroid_point))
            except Exception:
                # Skip problematic layers silently; the snapping fallback will still work with
                # the remaining successfully indexed layers.
                continue

        bundle = IndexBundle()
        if id_to_point:
            bundle.point_index = idx
            bundle.id_to_point = id_to_point
        else:
            bundle.point_index = None
            bundle.id_to_point = {}

        self.result_bundle = bundle
        return True

    def finished(self, ok):
        self.completed.emit()

    def _candidate_layers(self, visible_ids):
        for layer in QgsProject.instance().mapLayers().values():
            try:
                if self.only_visible and visible_ids is not None and layer.id() not in visible_ids:
                    continue
                if not isinstance(layer, QgsVectorLayer):
                    continue
                if not layer.isValid():
                    continue
                if layer.wkbType() == QgsWkbTypes.NoGeometry:
                    continue
            except Exception:
                continue
            yield layer

    def _prepare_layer_context(self, layer, target_crs, target_extent):
        transformer = None
        inverse_transform = None
        try:
            if target_crs is not None and target_crs.isValid() and layer.crs() != target_crs:
                transformer = QgsCoordinateTransform(layer.crs(), target_crs, QgsProject.instance())
                inverse_transform = QgsCoordinateTransform(target_crs, layer.crs(), QgsProject.instance())
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
    def _transform_point(transformer, point):
        if point is None:
            return None
        if transformer is None:
            return point
        try:
            return transformer.transform(point)
        except Exception:
            return None

    @staticmethod
    def _geometry_vertices(geom):
        try:
            for vertex in geom.vertices():
                yield QgsPointXY(vertex)
            return
        except Exception:
            pass

        for pt in CentroidIndexTask._fallback_vertices(geom):
            if pt is not None:
                yield pt

    @staticmethod
    def _fallback_vertices(geom):
        if geom is None or geom.isEmpty():
            return []

        try:
            wkb_type = geom.wkbType()
            geom_type = QgsWkbTypes.geometryType(wkb_type)
        except Exception:
            geom_type = QgsWkbTypes.UnknownGeometry

        if geom_type == QgsWkbTypes.PointGeometry:
            try:
                yield QgsPointXY(geom.asPoint())
            except Exception:
                try:
                    for pt in geom.asMultiPoint():
                        yield QgsPointXY(pt)
                except Exception:
                    return
        elif geom_type == QgsWkbTypes.LineGeometry:
            try:
                for pt in geom.asPolyline():
                    yield QgsPointXY(pt)
            except Exception:
                try:
                    for line in geom.asMultiPolyline():
                        for pt in line:
                            yield QgsPointXY(pt)
                except Exception:
                    return
        elif geom_type == QgsWkbTypes.PolygonGeometry:
            try:
                for ring in geom.asPolygon():
                    for pt in ring:
                        yield QgsPointXY(pt)
            except Exception:
                try:
                    for poly in geom.asMultiPolygon():
                        for ring in poly:
                            for pt in ring:
                                yield QgsPointXY(pt)
                except Exception:
                    return
        else:
            try:
                yield QgsPointXY(geom.asPoint())
            except Exception:
                return

    @staticmethod
    def _geometry_centroid(geom):
        try:
            centroid_geom = geom.centroid()
            if centroid_geom and not centroid_geom.isEmpty():
                return QgsPointXY(centroid_geom.asPoint())
        except Exception:
            return None
        return None
