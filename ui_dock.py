# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QComboBox,
    QHBoxLayout,
    QFormLayout,
)
from qgis.PyQt.QtCore import QSettings

class SettingsDock(QWidget):
    applyRequested = pyqtSignal()
    rebuildCentroidsRequested = pyqtSignal()

    def __init__(self, iface, settings_store: QSettings):
        super().__init__()
        self.iface = iface
        self.store = settings_store
        self._build_ui()
        self._load_from_store()

    def _build_ui(self):
        root = QVBoxLayout(self)

        form = QFormLayout()

        self.tol_value = QDoubleSpinBox()
        self.tol_value.setRange(0.1, 9999)
        self.tol_value.setDecimals(2)
        self.tol_units = QComboBox()
        self.tol_units.addItem("Pixels", "px")
        self.tol_units.addItem("Map units", "mu")
        tol_row = QWidget()
        tol_layout = QHBoxLayout(tol_row)
        tol_layout.setContentsMargins(0, 0, 0, 0)
        tol_layout.addWidget(self.tol_value)
        tol_layout.addWidget(self.tol_units)
        form.addRow("Snapping distance", tol_row)

        self.debounce = QSpinBox()
        self.debounce.setRange(0, 100)
        form.addRow("Delay before snapping (ms)", self.debounce)

        root.addLayout(form)

        self.chk_vert = QCheckBox("Snap to vertices")
        self.chk_segm = QCheckBox("Snap to edges")
        self.chk_cent = QCheckBox("Quick fallback snapping (all layers)")
        self.chk_build_cent = QCheckBox("Refresh quick index automatically")

        root.addWidget(self.chk_vert)
        root.addWidget(self.chk_segm)
        root.addWidget(self.chk_cent)
        root.addWidget(self.chk_build_cent)

        btn_apply = QPushButton("Apply & Activate")
        btn_rebuild = QPushButton("Rebuild index now")
        btn_apply.clicked.connect(self._on_apply_clicked)
        btn_rebuild.clicked.connect(self.rebuildCentroidsRequested.emit)

        root.addWidget(btn_apply)
        root.addWidget(btn_rebuild)
        root.addStretch(1)

        # defaults
        self.tol_value.setValue(12.0)
        self.tol_units.setCurrentIndex(0)
        self.chk_vert.setChecked(True)
        self.chk_segm.setChecked(True)
        self.chk_cent.setChecked(True)
        self.debounce.setValue(10)
        self.chk_build_cent.setChecked(True)

    def _on_apply_clicked(self):
        self._save_to_store()
        self.applyRequested.emit()

    def _k(self, x): return f"SnapZenPro/{x}"

    def _load_from_store(self):
        v = self.store.value(self._k("tolerance_value"), None)
        if v is not None:
            try: self.tol_value.setValue(float(v))
            except Exception: pass
        u = self.store.value(self._k("tolerance_units"), "px")
        if u == "mu":
            self.tol_units.setCurrentIndex(1)
        else:
            self.tol_units.setCurrentIndex(0)
        self.chk_vert.setChecked(self.store.value(self._k("snap_vertices"), True, type=bool))
        self.chk_segm.setChecked(self.store.value(self._k("snap_segments"), True, type=bool))

        if self.store.contains(self._k("use_fallback_index")):
            fallback = self.store.value(self._k("use_fallback_index"), True, type=bool)
        else:
            fallback = self.store.value(self._k("snap_centroids"), False, type=bool)
        self.chk_cent.setChecked(fallback)

        if self.store.contains(self._k("build_fallback_index")):
            build_idx = self.store.value(self._k("build_fallback_index"), True, type=bool)
        else:
            build_idx = self.store.value(self._k("build_centroid_index"), True, type=bool)
        self.chk_build_cent.setChecked(build_idx)

        self.debounce.setValue(self.store.value(self._k("debounce_ms"), 10, type=int))

    def _save_to_store(self):
        s = self.get_settings()
        for k, v in s.items():
            self.store.setValue(self._k(k), v)

    def get_settings(self):
        data = self.tol_units.currentData()
        units = data if data else ("px" if self.tol_units.currentIndex()==0 else "mu")
        fallback = self.chk_cent.isChecked()
        build_idx = self.chk_build_cent.isChecked()
        return {
            "tolerance_value": float(self.tol_value.value()),
            "tolerance_units": units,
            "debounce_ms": int(self.debounce.value()),
            "snap_vertices": self.chk_vert.isChecked(),
            "snap_segments": self.chk_segm.isChecked(),
            "use_fallback_index": fallback,
            "build_fallback_index": build_idx,
            # legacy keys kept for compatibility with earlier versions
            "snap_centroids": fallback,
            "build_centroid_index": build_idx,
        }
