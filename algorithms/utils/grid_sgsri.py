# -*- coding: utf-8 -*-

"""
/***************************************************************************
 OtomatisasiD3TLH
 Plugin yang membantu pengolahan D3TLH secara otomatis
                              -------------------
        begin                : 2025-08-15
        copyright            : (C) 2025 by Direktorat PDLKWS -
                               Deputi TLSDAB - Kementerian Lingkungan
                               Hidup/BPLH Republik Indonesia
        supported by         : Yayasan Lokus Bijak Hijau Lestari (LOKAHITA)
        email                : tech@yayasanlokahita.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = (
    "Fadillah Azhar Deaudin Kurniawan, "
    "Sitarani Safitri, Dini Aprilia Norvyani, "
    "Suchi Rahmadani, Fariz Rizaldy Wibowo"
)
__date__ = "2025-08-15"
__copyright__ = (
    "(C) 2025 by Direktorat PDLKWS - Deputi TLSDAB - "
    "Kementerian Lingkungan Hidup/BPLH Republik Indonesia"
)

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = "$Format:%H$"

import math
import processing
import os
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing, QgsProcessingException,
    QgsProcessingAlgorithm,
    QgsProcessingParameterExtent,
    QgsProcessingParameterEnum,
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterBoolean,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsFields,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsFeatureSink,
    QgsVectorLayer
)

# ORIGIN SGSRI
ORI_LAT_MIN = -15.0
ORI_LON_MIN = 90.0


class UtilsGridSGSRIAlgorithm(QgsProcessingAlgorithm):
    # Params
    P_EXTENT = "P_EXTENT"
    P_GRID_SIZE = "P_GRID_SIZE"
    P_CRS = "P_CRS"
    P_OUT = "P_OUT"

    # Admin/AOI (wajib layer; kab/prov wajib kolom)
    P_ADMIN_SRC = "P_ADMIN_SRC"
    P_F_DESA = "P_F_DESA"   # opsional
    P_F_KEC = "P_F_KEC"    # opsional
    P_F_KAB = "P_F_KAB"    # WAJIB
    P_F_PROV = "P_F_PROV"   # WAJIB

    # Clip hasil akhir ke AOI
    P_CLIP_AOI = "P_CLIP_AOI"

    GRID_CHOICES = [
        ("1° x 1°30' (~111.0 x 166.5 km)", 1.0, 1.5),
        ("30' x 30' (~55.50 x 55.50 km)", 0.5, 0.5),
        ("15' x 15' (~27.75 x 27.75 km)", 0.25, 0.25),
        ("7'30\" x 7'30\" (~13.875 x 13.875 km)", 0.125, 0.125),
        ("2'30\" x 2'30\" (~4.625 x 4.625 km)", 1.0 / 24.0, 1.0 / 24.0),
        ("30\" x 30\" (~0.900 x 0.900 km)", 1.0 / 120.0, 1.0 / 120.0),
        ("5\" x 5\" (~0.150 x 0.150 km)", 1.0 / 720.0, 1.0 / 720.0),
    ]

    # boilerplate

    def tr(self, s):
        return QCoreApplication.translate("Processing", s)

    def name(self):
        return self.tr(
            "grid_indonesia_generator"
        )

    def displayName(self):
        return self.tr(
            "Sistem Grid Skala Ragam Indonesia (SGSRI)"
        )

    def groupId(self):
        return self.tr("A. Utilities")

    def group(self):
        return self.tr(self.groupId())

    def createInstance(self):
        return UtilsGridSGSRIAlgorithm()

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(__file__),
                '01 Utilities.svg'
            )
        )

    def shortHelpString(self):
        return self.tr(
            """Sistem Grid Skala Ragam Indonesia (Indonesian Multi-scale Grid
                System/IMGS) dirancang sebagai struktur grid berbasis sel
                persegi yang menyerupai format data raster.Setiap sel memiliki
                koordinat unik dan atribut yang memungkinkan representasi
                fenomena geografis secara kontinu dan terstruktur. IMGS
                mengadopsi Sistem Referensi Geospasial Indonesia (SRGI) 2013
                sebagai acuan geodetik nasional, dengan titik asal pada
                90° BT dan 15° LS agar selaras dengan sistem
                penomoran lembar peta Rupa Bumi Indonesia (RBI).

                Pilihan ukuran GRID:
                • 1° × 1°30′ (≈111.0 × 166.5 km)
                • 30′ × 30′ (≈55.50 × 55.50 km)
                • 15′ × 15′ (≈27.75 × 27.75 km)
                • 7′30″ × 7′30″ (≈13.875 × 13.875 km)
                • 2′30″ × 2′30″ (≈4.625 × 4.625 km)
                • 30″ × 30″ (≈0.900 × 0.900 km)
                • 5″ × 5″ (≈0.150 × 0.150 km)

                Selain itu juga ada penambahan kolom batas administrasi mulai
                dari desa/kelurahan hingga provinsi dari
                input Batas Administrasi

                Keluaran akhir SGSRI terdiri dari kolom/field: id,
                WADMKD, WADMKC, WADMKK, WADMPR."""
        )

    # parameter UI
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterExtent(
            self.P_EXTENT, self.tr("Extent pembuatan grid (EPSG:4326)")
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.P_GRID_SIZE, self.tr("Ukuran grid"),
            options=[c[0] for c in self.GRID_CHOICES], defaultValue=5
        ))
        self.addParameter(QgsProcessingParameterCrs(
            self.P_CRS, self.tr("CRS keluaran"),
            defaultValue=QgsCoordinateReferenceSystem("EPSG:4326"),
            optional=True
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.P_OUT, self.tr("SGSRI"),
            type=QgsProcessing.TypeVectorPolygon
        ))

        # Layer admin/AOI WAJIB
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.P_ADMIN_SRC, self.tr(
                "Batas administrasi atau Area of Interest (AOI)"),
            [QgsProcessing.TypeVectorPolygon],
            optional=False
        ))
        # Kolom opsional
        self.addParameter(QgsProcessingParameterField(
            self.P_F_DESA, self.tr("Kolom Desa/Kelurahan"),
            parentLayerParameterName=self.P_ADMIN_SRC, optional=True,
            type=QgsProcessingParameterField.Any
        ))
        self.addParameter(QgsProcessingParameterField(
            self.P_F_KEC, self.tr("Kolom Kecamatan"),
            parentLayerParameterName=self.P_ADMIN_SRC, optional=True,
            type=QgsProcessingParameterField.Any
        ))
        # Kolom WAJIB
        self.addParameter(QgsProcessingParameterField(
            self.P_F_KAB, self.tr("Kolom Kabupaten/Kota (Contoh: WADMKK)"),
            parentLayerParameterName=self.P_ADMIN_SRC, optional=False,
            type=QgsProcessingParameterField.Any
        ))
        self.addParameter(QgsProcessingParameterField(
            self.P_F_PROV, self.tr("Kolom Provinsi (Contoh: WADMPR)"),
            parentLayerParameterName=self.P_ADMIN_SRC, optional=False,
            type=QgsProcessingParameterField.Any
        ))

        # Checkbox clip AOI
        self.addParameter(QgsProcessingParameterBoolean(
            self.P_CLIP_AOI,
            self.tr("Clip hasil akhir ke Batas Administrasi atau AOI"),
            defaultValue=False
        ))

    # helper penamaan
    @staticmethod
    def _pad2(v: int) -> str:
        return f"{v:02d}"

    @staticmethod
    def _isclose(a, b):
        return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12)

    def _make_hier_id_from_index(
            self, x_sw: float, y_sw: float,
            d_lat: float, d_lon: float) -> str:
        # indeks global berbasis 5 detik dari origin SGSRI
        base = 1.0 / 720.0

        gx = int(round((x_sw - ORI_LON_MIN) / base))
        gy = int(round((y_sw - ORI_LAT_MIN) / base))

        # 1° x 1°30′
        K = gx // 1080 + 1        # 1.5 derajat = 1080 cell 5"
        B = gy // 720 + 1         # 1 derajat = 720 cell 5"

        rx = gx % 1080
        ry = gy % 720

        # 30′ x 30′
        M = rx // 360 + 1
        N = ry // 360 + 1
        C = M + (N - 1) * 3

        rx = rx % 360
        ry = ry % 360

        # 15′ x 15′
        O1 = rx // 180 + 1
        P = ry // 180 + 1
        D = O1 + (P - 1) * 2

        rx = rx % 180
        ry = ry % 180

        # 7′30″ x 7′30″
        Q = rx // 90 + 1
        R = ry // 90 + 1
        E = Q + (R - 1) * 2

        rx = rx % 90
        ry = ry % 90

        # 2′30″ x 2′30″
        S = rx // 30 + 1
        T = ry // 30 + 1
        F = S + (T - 1) * 3

        rx = rx % 30
        ry = ry % 30

        # 30″ x 30″
        I30 = rx // 6 + 1
        N30 = ry // 6 + 1
        G = I30 + (N30 - 1) * 5

        rx = rx % 6
        ry = ry % 6

        # 5″ x 5″
        U = rx + 1
        V = ry + 1
        H = U + (V - 1) * 6

        kb = self._pad2(K) + self._pad2(B)

        if self._isclose(d_lat, 1.0) and self._isclose(d_lon, 1.5):
            return kb
        if self._isclose(d_lat, 0.5) and self._isclose(d_lon, 0.5):
            return kb + str(C)
        if self._isclose(d_lat, 0.25) and self._isclose(d_lon, 0.25):
            return kb + str(C) + str(D)
        if self._isclose(d_lat, 0.125) and self._isclose(d_lon, 0.125):
            return kb + str(C) + str(D) + str(E)
        if self._isclose(d_lat, 1 / 24) and self._isclose(d_lon, 1 / 24):
            return kb + str(C) + str(D) + str(E) + str(F)
        if self._isclose(d_lat, 1 / 120) and self._isclose(d_lon, 1 / 120):
            a = kb
            b = str(C)
            c = str(D)
            d = str(E)
            e = str(F)
            f = f"{G:02d}"
            return a + b + c + d + e + f
        if self._isclose(d_lat, 1 / 720) and self._isclose(d_lon, 1 / 720):
            a = kb
            b = str(C)
            c = str(D)
            d = str(E)
            e = str(F)
            f = f"{G:02d}"
            g = f"{H:02d}"
            return a + b + c + d + e + f + g

        return kb

    # MCA helper
    def _mca_one_field(
            self, grid_layer, admin_layer,
            id_field, src_field, feedback):
        inter1 = processing.run(
            "qgis:intersection",
            {"INPUT": grid_layer, "OVERLAY": admin_layer,
             "INPUT_FIELDS": [id_field],
             "OVERLAY_FIELDS": [src_field],
             "OVERLAY_FIELDS_PREFIX": "",
             "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            feedback=feedback
        )["OUTPUT"]

        dissolved = processing.run(
            "qgis:dissolve",
            {"INPUT": inter1,
             "FIELD": [id_field, src_field],
             "SEPARATE_DISJOINT": False,
             "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            feedback=feedback
        )["OUTPUT"]

        with_area = processing.run(
            "qgis:fieldcalculator",
            {"INPUT": dissolved, "FIELD_NAME": "lglcha", "FIELD_TYPE": 1,
             "FIELD_LENGTH": 20, "FIELD_PRECISION": 3, "NEW_FIELD": True,
             "FORMULA": "$area", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            feedback=feedback
        )["OUTPUT"]

        stats = processing.run(
            "qgis:statisticsbycategories",
            {"INPUT": with_area,
             "CATEGORIES_FIELD_NAME": [id_field],
             "VALUES_FIELD_NAME": "lglcha",
             "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            feedback=feedback
        )["OUTPUT"]

        stats_ren = processing.run(
            "qgis:renametablefield",
            {"INPUT": stats, "FIELD": "max", "NEW_NAME": "lglcha_max",
             "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            feedback=feedback
        )["OUTPUT"]

        join_max = processing.run(
            "qgis:joinattributestable",
            {"INPUT": with_area,
             "FIELD": id_field,
             "INPUT_2": stats_ren,
             "FIELD_2": id_field,
             "FIELDS_TO_COPY": ["lglcha_max"],
             "METHOD": 0,
             "DISCARD_NONMATCHING": False,
             "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            feedback=feedback
        )["OUTPUT"]

        winners = processing.run(
            "qgis:extractbyexpression",
            {"INPUT": join_max, "EXPRESSION": "\"lglcha\" = \"lglcha_max\"",
             "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            feedback=feedback
        )["OUTPUT"]

        table_winner = processing.run(
            "qgis:dropgeometries",
            {"INPUT": winners, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            feedback=feedback
        )["OUTPUT"]

        grid_join = processing.run(
            "qgis:joinattributestable",
            {"INPUT": grid_layer, "FIELD": id_field, "INPUT_2": table_winner,
             "FIELD_2": id_field,
             "FIELDS_TO_COPY": [src_field],
             "METHOD": 0, "DISCARD_NONMATCHING": False,
             "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            feedback=feedback
        )["OUTPUT"]

        # pastikan nama kolom sama dgn src_field
        before = [f.name() for f in grid_layer.fields()]
        after = [
            f.name() for f in grid_join.fields()]
        added = [n for n in after if n not in before]
        joined_name = added[0] if added else src_field
        if joined_name != src_field:
            grid_join = processing.run(
                "qgis:renametablefield",
                {"INPUT": grid_join,
                 "FIELD": joined_name,
                 "NEW_NAME": src_field,
                 "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
                feedback=feedback
            )["OUTPUT"]

        return grid_join

    # main
    def processAlgorithm(self, parameters, context, feedback):
        extent = self.parameterAsExtent(parameters, self.P_EXTENT, context)
        size_idx = self.parameterAsEnum(parameters, self.P_GRID_SIZE, context)
        crs_out = self.parameterAsCrs(parameters, self.P_CRS, context)
        if not crs_out.isValid():
            crs_out = QgsCoordinateReferenceSystem("EPSG:4326")
        label, d_lat, d_lon = self.GRID_CHOICES[size_idx]

        # Admin/AOI (wajib)
        admin_vl = self.parameterAsVectorLayer(
            parameters, self.P_ADMIN_SRC, context)
        if admin_vl is None:
            raise QgsProcessingException(self.tr(
                "Layer batas administrasi/AOI wajib diisi."))

        f_desa = self.parameterAsString(
            parameters, self.P_F_DESA, context) or None
        f_kec = self.parameterAsString(
            parameters, self.P_F_KEC, context) or None
        f_kab = self.parameterAsString(
            parameters, self.P_F_KAB, context) or None
        f_prov = self.parameterAsString(
            parameters, self.P_F_PROV, context) or None
        if not f_kab or not f_prov:
            raise QgsProcessingException(
                self.tr(
                    "Kolom Kabupaten/Kota (WADMKK) dan "
                    "Provinsi (WADMPR) wajib dipilih."))

        do_clip = self.parameterAsBool(parameters, self.P_CLIP_AOI, context)

        wanted_fields = [
            ("WADMKD", f_desa),
            ("WADMKC", f_kec),
            ("WADMKK", f_kab),
            ("WADMPR", f_prov)
        ]

        # snap extent ke grid origin
        def snap_down(v, origin, step):
            return origin + math.floor((v - origin) / step) * step

        xmin = snap_down(extent.xMinimum(), ORI_LON_MIN, d_lon)
        ymin = snap_down(extent.yMinimum(), ORI_LAT_MIN, d_lat)
        xmax = extent.xMaximum()
        ymax = extent.yMaximum()

        # bangun GRID (memory)
        fields = QgsFields()
        for name, typ in [
            ("id", QVariant.String),
            ("col", QVariant.Int),
            ("row", QVariant.Int),
            ("lon_min", QVariant.Double),
            ("lat_min", QVariant.Double),
            ("lon_max", QVariant.Double),
            ("lat_max", QVariant.Double),
            ("step_lat", QVariant.Double),
            ("step_lon", QVariant.Double),
            ("grid_lbl", QVariant.String),
        ]:
            fields.append(QgsField(name, typ))

        mem_grid = QgsVectorLayer(f"Polygon?crs={crs_out.authid()}",
                                  "grid_tmp", "memory")
        provdr = mem_grid.dataProvider()
        provdr.addAttributes(fields)
        mem_grid.updateFields()

        ncols = int(math.ceil((xmax - xmin) / d_lon))
        nrows = int(math.ceil((ymax - ymin) / d_lat))

        for iy in range(nrows):
            y = round(ymin + iy * d_lat, 12)

            for ix in range(ncols):
                x = round(xmin + ix * d_lon, 12)

                col = int(round((x - ORI_LON_MIN) / d_lon))
                row = int(round((y - ORI_LAT_MIN) / d_lat))

                x2 = round(x + d_lon, 12)
                y2 = round(y + d_lat, 12)

                poly = QgsGeometry.fromPolygonXY([[
                    QgsPointXY(x, y),
                    QgsPointXY(x2, y),
                    QgsPointXY(x2, y2),
                    QgsPointXY(x, y2),
                    QgsPointXY(x, y),
                ]])

                grid_id = self._make_hier_id_from_index(x, y, d_lat, d_lon)

                f = QgsFeature(mem_grid.fields())
                f.setGeometry(poly)
                f["id"] = grid_id
                f["col"] = col
                f["row"] = row
                f["lon_min"] = x
                f["lat_min"] = y
                f["lon_max"] = x2
                f["lat_max"] = y2
                f["step_lat"] = d_lat
                f["step_lon"] = d_lon
                f["grid_lbl"] = label
                provdr.addFeatures([f])
        mem_grid.updateExtents()

        processing.run(
            "qgis:createspatialindex",
            {"INPUT": admin_vl},
            feedback=feedback
        )

        processing.run(
            "qgis:createspatialindex",
            {"INPUT": mem_grid},
            feedback=feedback
        )

        #  AOI: Extract by Location (Intersects)
        grid_for_join = processing.run(
            "qgis:extractbylocation",
            {"INPUT": mem_grid, "PREDICATE": [0], "INTERSECT": admin_vl,
             "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            feedback=feedback
        )["OUTPUT"]

        #  MCA berantai
        for out_name, src_field in wanted_fields:
            if not src_field:
                continue
            if out_name in [f.name() for f in grid_for_join.fields()]:
                grid_for_join = processing.run(
                    "qgis:deletecolumn",
                    {"INPUT": grid_for_join, "COLUMN": [out_name],
                     "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
                    feedback=feedback
                )["OUTPUT"]
            tmp = self._mca_one_field(grid_for_join, admin_vl, "id",
                                      src_field, feedback)
            if src_field != out_name:
                tmp = processing.run(
                    "qgis:renametablefield",
                    {"INPUT": tmp, "FIELD": src_field, "NEW_NAME": out_name,
                     "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
                    feedback=feedback
                )["OUTPUT"]
            grid_for_join = tmp

        #  pastikan kolom output lengkap
        need_cols = ["WADMKD", "WADMKC", "WADMKK", "WADMPR"]
        existing = [f.name() for f in grid_for_join.fields()]
        for cname in need_cols:
            if cname not in existing:
                grid_for_join = processing.run(
                    "qgis:fieldcalculator",
                    {"INPUT": grid_for_join, "FIELD_NAME": cname,
                     "FIELD_TYPE": 2, "FIELD_LENGTH": 254,
                     "NEW_FIELD": True, "FORMULA": "NULL",
                     "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
                    feedback=feedback
                )["OUTPUT"]

        #  refactor fields: fix urutan dan tipe
        schema = [
            {
                "name": "ID",
                "type": 10,
                "length": 254,
                "precision": 0,
                "expression": '"ID"',
            },
            {
                "name": "WADMKD",
                "type": 10,
                "length": 254,
                "precision": 0,
                "expression": '"WADMKD"',
            },
            {
                "name": "WADMKC",
                "type": 10,
                "length": 254,
                "precision": 0,
                "expression": '"WADMKC"',
            },
            {
                "name": "WADMKK",
                "type": 10,
                "length": 254,
                "precision": 0,
                "expression": '"WADMKK"',
            },
            {
                "name": "WADMPR",
                "type": 10,
                "length": 254,
                "precision": 0,
                "expression": '"WADMPR"',
            },
        ]
        final_layer = processing.run(
            "qgis:refactorfields",
            {"INPUT": grid_for_join, "FIELDS_MAPPING": schema,
             "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            feedback=feedback
        )["OUTPUT"]

        #  (opsional) CLIP ke AOI
        if do_clip:
            final_layer = processing.run(
                "qgis:clip",
                {"INPUT": final_layer, "OVERLAY": admin_vl,
                 "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
                feedback=feedback
            )["OUTPUT"]

        #  tulis ke output sink
        out_fields = final_layer.fields()
        sink, dest_id = self.parameterAsSink(
            parameters, self.P_OUT, context,
            out_fields, final_layer.wkbType(),
            final_layer.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException(self.tr(
                "Tidak dapat membuat output sink."))

        for ft in final_layer.getFeatures():
            sink.addFeature(ft, QgsFeatureSink.FastInsert)

        return {self.P_OUT: dest_id}
