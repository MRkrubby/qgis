# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QDoubleSpinBox,
                                 QSpinBox, QCheckBox, QPushButton, QComboBox)
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

        # Tolerance
        g_tol = QGroupBox("Snapping tolerance")
        gl = QGridLayout(g_tol)
        gl.addWidget(QLabel("Value:"), 0, 0)
        self.tol_value = QDoubleSpinBox(); self.tol_value.setRange(0.1, 9999); self.tol_value.setDecimals(2)
        gl.addWidget(self.tol_value, 0, 1)
        gl.addWidget(QLabel("Units:"), 0, 2)
        self.tol_units = QComboBox(); self.tol_units.addItems(["pixels", "map units"])
        gl.addWidget(self.tol_units, 0, 3)

        # Modes
        g_modes = QGroupBox("Snap modes")
        gm = QGridLayout(g_modes)
        self.chk_vert = QCheckBox("Vertices")
        self.chk_segm = QCheckBox("Segments")
        self.chk_cent = QCheckBox("Centroids (fallback)")
        gm.addWidget(self.chk_vert, 0, 0); gm.addWidget(self.chk_segm, 0, 1); gm.addWidget(self.chk_cent, 0, 2)

        # Performance
        g_perf = QGroupBox("Performance")
        gp = QGridLayout(g_perf)
        self.debounce = QSpinBox(); self.debounce.setRange(0, 100)
        gp.addWidget(QLabel("Debounce (ms):"), 0, 0); gp.addWidget(self.debounce, 0, 1)
        self.chk_build_cent = QCheckBox("Build centroid index in background")
        gp.addWidget(self.chk_build_cent, 1, 0, 1, 2)

        # Buttons
        btn_apply = QPushButton("Apply / Activate")
        btn_rebuild = QPushButton("Rebuild centroids now")
        btn_apply.clicked.connect(self._on_apply_clicked)
        btn_rebuild.clicked.connect(self.rebuildCentroidsRequested.emit)

        root.addWidget(g_tol)
        root.addWidget(g_modes)
        root.addWidget(g_perf)
        root.addWidget(btn_apply)
        root.addWidget(btn_rebuild)
        root.addStretch(1)

        # defaults
        self.tol_value.setValue(12.0)
        self.tol_units.setCurrentIndex(0)
        self.chk_vert.setChecked(True)
        self.chk_segm.setChecked(True)
        self.chk_cent.setChecked(False)
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
        self.tol_units.setCurrentIndex(0 if u=="px" else 1)
        self.chk_vert.setChecked(self.store.value(self._k("snap_vertices"), True, type=bool))
        self.chk_segm.setChecked(self.store.value(self._k("snap_segments"), True, type=bool))
        self.chk_cent.setChecked(self.store.value(self._k("snap_centroids"), False, type=bool))
        self.debounce.setValue(self.store.value(self._k("debounce_ms"), 10, type=int))
        self.chk_build_cent.setChecked(self.store.value(self._k("build_centroid_index"), True, type=bool))

    def _save_to_store(self):
        s = self.get_settings()
        for k, v in s.items():
            self.store.setValue(self._k(k), v)

    def get_settings(self):
        units = "px" if self.tol_units.currentIndex()==0 else "mu"
        return {
            "tolerance_value": float(self.tol_value.value()),
            "tolerance_units": units,
            "debounce_ms": int(self.debounce.value()),
            "snap_vertices": self.chk_vert.isChecked(),
            "snap_segments": self.chk_segm.isChecked(),
            "snap_centroids": self.chk_cent.isChecked(),
            "build_centroid_index": self.chk_build_cent.isChecked(),
        }
