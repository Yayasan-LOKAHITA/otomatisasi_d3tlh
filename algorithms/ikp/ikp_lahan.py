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

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
)
import processing
import os
from qgis.PyQt.QtGui import QIcon


class IKPLahanAlgorithm(QgsProcessingAlgorithm):
    # Parameters
    P_GRID_SGSRI = "P_GRID_SGSRI"  # GRID SGSRI (kolom minimal: ID)
    P_JLH_KPGN = (
        "P_JLH_KPGN"  # JLH Penyedia Pangan (kolom: PULAU, KPGN_YY)
    )
    P_PL = "P_PL"  # Penutup Lahan (PL)
    P_KWSHUTAN = "P_KWSHUTAN"  # Kawasan Hutan (kwshutan)
    P_GRID_POP = (
        "P_GRID_POP"  # GRID Distribusi Penduduk (kolom: ID, POPGRIDYY)
    )
    P_YEAR = "P_YEAR"  # Tahun (e.g., 2024 → kolom suffix 24)
    P_JEP = "P_JEP"  # Jejak Ekologis Pangan (SJEPGN)
    P_JEB = "P_JEB"  # Jejak Ekologis Built-Up Land (SJEBUILT)

    # Outputs
    OUTPUT_IKP = "OUTPUT_IKP"  # Layer IKP per GRID
    OUTPUT_KETER = (
        "OUTPUT_KETER"  # Layer poligon Ketersediaan Lahan (pra-grid)
    )

    def tr(self, s):
        return QCoreApplication.translate("Processing", s)

    # Metadata
    def name(self):
        return "ikp_lahan"

    def displayName(self):
        return self.tr("IKP Lahan")

    def groupId(self):
        return "E. Indeks Kemampuan Pemanfaatan (IKP)"

    def group(self):
        return self.tr(self.groupId())

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(__file__), "05 Carrying Capacity.svg"
            )
        )

    def shortHelpString(self):
        return self.tr(
            "This module calculates the Land Utilization Capability Index "
            "(IKP Lahan), an indicator used to assess the capability of land "
            "resources to support basic human needs, particularly food "
            "production and settlement functions, while maintaining "
            "ecological sustainability.\n\n"
            "The methodology integrates ecosystem service provision, land "
            "cover characteristics, forest functions, ecological footprint "
            "indicators, and population pressure to estimate land "
            "availability and utilization capacity.\n\n"
            "The resulting index can be used to evaluate environmental "
            "carrying capacity, land-use suitability, and ecological "
            "sustainability within D3TLH assessments.\n\n"
            "<b>Complete explanation read here: "
            "<a href='https://yayasan-lokahita.github.io/"
            "otomatisasi_d3tlh-docs/ikp/ikp_lahan/'>here</a>.</b>"
        )

    def createInstance(self):
        return IKPLahanAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.P_GRID_SGSRI,
                self.tr('Data Grid [Dengan Kolom "ID" dan "WADMKK"]'),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.P_JLH_KPGN,
                self.tr(
                    'Grid JLH Penyedia Pangan [Dengan kolom "PULAU" dan '
                    '"PGN_YY, YY adalah dua digit terakhir tahun."]'
                ),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.P_PL,
                self.tr('Data Penutup Lahan [Dengan Kolom "PL"]'),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.P_KWSHUTAN,
                self.tr('Kawasan Hutan [Dengan kolom "kwshutan"]'),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.P_GRID_POP,
                self.tr(
                    'Grid Distribusi Penduduk [Dengan kolom "ID" '
                    'dan "POPGRID_YY"]'
                ),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.P_YEAR,
                self.tr("Tahun Analisis [Contoh: 2024]"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=2024,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.P_JEP,
                self.tr("Jejak Ekologis Pangan (SJEPGN)"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.0623630,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.P_JEB,
                self.tr("Jejak Ekologis Built-Up Land (SJEBUILT)"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.0024956,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_KETER,
                self.tr(
                    'Ketersediaan Lahan dalam hektar [kolom "KET_HA"]'
                ),
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_IKP,
                self.tr('IKP Lahan Grid [kolom "IKPLHN"]'),
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # === Params & derived fields
        grid_src = parameters[self.P_GRID_SGSRI]
        jlh_src = parameters[self.P_JLH_KPGN]
        pl_src = parameters[self.P_PL]
        kwsh_src = parameters[self.P_KWSHUTAN]
        grid_pop_src = parameters[self.P_GRID_POP]
        year = int(
            self.parameterAsDouble(parameters, self.P_YEAR, context)
        )
        sjepgn = float(
            self.parameterAsDouble(parameters, self.P_JEP, context)
        )
        sjebuilt = float(
            self.parameterAsDouble(parameters, self.P_JEB, context)
        )

        yy = f"{year % 100:02d}"  # 2024 -> '24'
        fld_kpgn = f"KPGN_{yy}"
        fld_pop = f"POPGRID{yy}"

        # CRS patokan = CRS GRID
        grid_src_layer = self.parameterAsSource(
            parameters, self.P_GRID_SGSRI, context
        )
        crs_out = grid_src_layer.sourceCrs()

        # Helper: buat index aman
        def _make_index(layer):
            try:
                processing.run(
                    "native:createspatialindex",
                    {"INPUT": layer},
                    context=context,
                    feedback=feedback,
                )
            except Exception:
                pass

        # === Normalisasi CRS (semua ke CRS GRID) + fix + index
        def _reproj_fix_index(inp):
            out = processing.run(
                "native:reprojectlayer",
                {
                    "INPUT": inp,
                    "TARGET_CRS": crs_out,
                    "OUTPUT": "TEMPORARY_OUTPUT",
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            out = processing.run(
                "native:fixgeometries",
                {"INPUT": out, "OUTPUT": "TEMPORARY_OUTPUT"},
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            _make_index(out)
            return out

        grid_src = _reproj_fix_index(
            grid_src
        )  # aman kalau sudah sama CRS
        jlh_src = _reproj_fix_index(jlh_src)
        pl_src = _reproj_fix_index(pl_src)
        kwsh_src = _reproj_fix_index(kwsh_src)
        # grid_pop_src hanya untuk join atribut → tidak wajib reproj,
        # tapi aman tidak mengganggu

        # Extent GRID (untuk subset cepat)
        extent_poly = processing.run(
            "native:polygonfromlayerextent",
            {"INPUT": grid_src, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Subset tanpa memotong
        jlh_sub = processing.run(
            "native:extractbylocation",
            {
                "INPUT": jlh_src,
                "PREDICATE": [0],
                "INTERSECT": extent_poly,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        pl_sub = processing.run(
            "native:extractbylocation",
            {
                "INPUT": pl_src,
                "PREDICATE": [0],
                "INTERSECT": extent_poly,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        kwsh_sub = processing.run(
            "native:extractbylocation",
            {
                "INPUT": kwsh_src,
                "PREDICATE": [0],
                "INTERSECT": extent_poly,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Fix lagi (aman)
        jlh_sub = processing.run(
            "native:fixgeometries",
            {"INPUT": jlh_sub, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        pl_sub = processing.run(
            "native:fixgeometries",
            {"INPUT": pl_sub, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        kwsh_sub = processing.run(
            "native:fixgeometries",
            {"INPUT": kwsh_sub, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        _make_index(jlh_sub)
        _make_index(pl_sub)
        _make_index(kwsh_sub)

        # Filter PL yang diperbolehkan
        pl_allowed = processing.run(
            "native:extractbyexpression",
            {
                "INPUT": pl_sub,
                "EXPRESSION": """
                    PL NOT IN ('Pertambangan','Bandara/Pelabuhan')
                """,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        pl_allowed = processing.run(
            "native:fixgeometries",
            {"INPUT": pl_allowed, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        _make_index(pl_allowed)

        # Dissolve kwshutan agar overlay lebih stabil
        kwsh_dis = processing.run(
            "native:dissolve",
            {
                "INPUT": kwsh_sub,
                "FIELD": ["kwshutan"],
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        kwsh_dis = processing.run(
            "native:fixgeometries",
            {"INPUT": kwsh_dis, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        _make_index(kwsh_dis)

        # === Bangun poligon pra-grid (bawa PL, kwshutan, dan KPGN_YY):
        # step1: PL_allowed ∩ kwsh_dis
        inter1 = processing.run(
            "native:intersection",
            {
                "INPUT": pl_allowed,
                "OVERLAY": kwsh_dis,
                "INPUT_FIELDS": [],
                "OVERLAY_FIELDS": [],
                "OVERLAY_FIELDS_PREFIX": "",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        inter1 = processing.run(
            "native:fixgeometries",
            {"INPUT": inter1, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        _make_index(inter1)

        # step2: (inter1) ∩ JLH (agar KPGN_YY ikut)
        inter2 = processing.run(
            "native:intersection",
            {
                "INPUT": inter1,
                "OVERLAY": jlh_sub,
                "INPUT_FIELDS": [],
                "OVERLAY_FIELDS": [],
                "OVERLAY_FIELDS_PREFIX": "",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        inter2 = processing.run(
            "native:fixgeometries",
            {"INPUT": inter2, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        _make_index(inter2)

        # Keep fields yang dibutuhkan
        keep_fields = ["PL", "kwshutan", fld_kpgn, "PULAU"]
        inter_keep = processing.run(
            "native:retainfields",
            {
                "INPUT": inter2,
                "FIELDS": keep_fields,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # REMARK rules:
        # Ketersediaan Lahan Pangan dan Hunian:
        #   KPGN in (Sedang, Tinggi, Sangat Tinggi)
        #   PL tidak dalam ('Pertambangan','Bandara/Pelabuhan')
        #   kwshutan dalam set diizinkan
        # Ketersediaan Lahan Hunian:
        #   KPGN in (Rendah, Sangat Rendah)
        #   PL dalam ('Permukiman','Lahan Terbuka','Permukiman Transmigrasi')
        #   kwshutan dalam set diizinkan
        # Selain itu: Lahan Tidak Dihitung
        allowed_kw = (
            "'Hutan Lindung','Hutan Produksi','Hutan Produksi Terbatas',"
            "'Hutan Produksi yang dapat Dikonversi','Areal Penggunaan Lain',"
            "'Danau','Tubuh Air'"
        )
        expr_remark = (
            "CASE "
            f"WHEN (\"{fld_kpgn}\" IN ('Sedang','Tinggi','Sangat Tinggi') "
            "AND (PL NOT IN ('Pertambangan','Bandara/Pelabuhan')) "
            f"AND (kwshutan IN ({allowed_kw}))) "
            "THEN 'Ketersediaan Lahan Pangan dan Hunian' "
            f"WHEN (\"{fld_kpgn}\" IN ('Rendah','Sangat Rendah') "
            "AND (PL IN ('Permukiman','Lahan Terbuka',"
            "'Permukiman Transmigrasi')) "
            f"AND (kwshutan IN ({allowed_kw}))) "
            "THEN 'Ketersediaan Lahan Hunian' "
            "ELSE 'Lahan Tidak Dihitung' END"
        )
        ket_pol = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": inter_keep,
                "FIELD_NAME": "REMARK",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 255,
                "FIELD_PRECISION": 0,
                "NEW_FIELD": True,
                "FORMULA": expr_remark,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Hitung luas dalam EPSG:3395, lalu kembali ke CRS GRID
        ket_3395 = processing.run(
            "native:reprojectlayer",
            {
                "INPUT": ket_pol,
                "TARGET_CRS": "EPSG:3395",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        ket_3395 = processing.run(
            "native:fixgeometries",
            {"INPUT": ket_3395, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        ket_area = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": ket_3395,
                "FIELD_NAME": "AREAHA",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 6,
                "NEW_FIELD": True,
                "FORMULA": "$area / 10000",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        ket_pol_out = processing.run(
            "native:reprojectlayer",
            {
                "INPUT": ket_area,
                "TARGET_CRS": crs_out,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        ket_pol_out_1 = processing.run(
            "native:fixgeometries",
            {"INPUT": ket_pol_out, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        _make_index(ket_pol_out_1)

        # Retain kolom untuk OUTPUT_KETER
        ket_pol_out_2 = processing.run(
            "native:retainfields",
            {
                "INPUT": ket_pol_out_1,
                "FIELDS": [
                    fld_kpgn,
                    "PL",
                    "kwshutan",
                    "REMARK",
                    "AREAHA",
                    "PULAU",
                ],
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # === IKP per GRID ===
        # Ambil hanya REMARK Pangan/Hunian untuk dihitung sebagai KET_HA
        ket_val = processing.run(
            "native:extractbyexpression",
            {
                "INPUT": ket_pol_out_2,
                "EXPRESSION": """
                    \"REMARK\" IN ('Ketersediaan Lahan Pangan dan Hunian',
                    'Ketersediaan Lahan Hunian')
                """,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        _make_index(ket_val)

        # GRID yang beririsan “ket_val”, lalu potong
        grid_sub = processing.run(
            "native:extractbylocation",
            {
                "INPUT": grid_src,
                "PREDICATE": [0],
                "INTERSECT": ket_val,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        grid_sub = processing.run(
            "native:fixgeometries",
            {"INPUT": grid_sub, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        _make_index(grid_sub)
        _make_index(ket_val)

        inter_grid = processing.run(
            "native:intersection",
            {
                "INPUT": grid_sub,
                "OVERLAY": ket_val,
                "INPUT_FIELDS": [],
                "OVERLAY_FIELDS": [],
                "OVERLAY_FIELDS_PREFIX": "",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        inter_grid = processing.run(
            "native:fixgeometries",
            {"INPUT": inter_grid, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Luas hasil potong di 3395, kembali ke CRS GRID (supaya konsisten)
        inter_3395 = processing.run(
            "native:reprojectlayer",
            {
                "INPUT": inter_grid,
                "TARGET_CRS": "EPSG:3395",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        inter_3395 = processing.run(
            "native:fixgeometries",
            {"INPUT": inter_3395, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        inter_area = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": inter_3395,
                "FIELD_NAME": "AREAHA",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 6,
                "NEW_FIELD": True,
                "FORMULA": "$area / 10000",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        inter_back = processing.run(
            "native:reprojectlayer",
            {
                "INPUT": inter_area,
                "TARGET_CRS": crs_out,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Pastikan ID ada di grid_sub/inter_back; agregasi SUM AREAHA per ID
        # Pertama, bawa kolom ID (kalau hilang) -> biasanya masih ada dari GRID
        keep4sum = processing.run(
            "native:retainfields",
            {
                "INPUT": inter_back,
                "FIELDS": ["ID", "AREAHA"],
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        stats = processing.run(
            "qgis:statisticsbycategories",
            {
                "INPUT": keep4sum,
                "CATEGORIES_FIELD_NAME": ["ID"],
                "VALUES_FIELD_NAME": "AREAHA",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        ket_tbl = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": stats,
                "FIELD_NAME": "KET_HA",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 6,
                "NEW_FIELD": True,
                "FORMULA": 'coalesce("sum",0)',
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        ket_keep = processing.run(
            "native:retainfields",
            {
                "INPUT": ket_tbl,
                "FIELDS": ["ID", "KET_HA"],
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Join KET_HA ke GRID SGSRI penuh
        joined1 = processing.run(
            "native:joinattributestable",
            {
                "INPUT": grid_src,
                "FIELD": "ID",
                "INPUT_2": ket_keep,
                "FIELD_2": "ID",
                "FIELDS_TO_COPY": ["KET_HA"],
                "METHOD": 1,
                "DISCARD_NONMATCHING": False,
                "PREFIX": "",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Join POPGRIDYY dan WADMKK: pakai ID string agar aman
        grid_key = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": joined1,
                "FIELD_NAME": "ID_KEY",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 64,
                "FIELD_PRECISION": 0,
                "NEW_FIELD": True,
                "FORMULA": 'trim(to_string("ID"))',
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        pop_key = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": grid_pop_src,
                "FIELD_NAME": "ID_KEY",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 64,
                "FIELD_PRECISION": 0,
                "NEW_FIELD": True,
                "FORMULA": 'trim(to_string("ID"))',
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        try:
            processing.run(
                "native:createattributeindex",
                {"INPUT": pop_key, "FIELD": "ID_KEY"},
                context=context,
                feedback=feedback,
            )
        except Exception:
            pass

        joined2 = processing.run(
            "native:joinattributestable",
            {
                "INPUT": grid_key,
                "FIELD": "ID_KEY",
                "INPUT_2": pop_key,
                "FIELD_2": "ID_KEY",
                "FIELDS_TO_COPY": [
                    fld_pop,
                    "WADMKK",
                ],  # ← TAMBAH WADMKK DI SINI
                "METHOD": 1,
                "DISCARD_NONMATCHING": False,
                "PREFIX": "",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Bangun basis kolom IKP (tanpa REMARK)
        # Bangun basis kolom IKP (setelah joined2)
        base = processing.run(
            "native:retainfields",
            {
                "INPUT": joined2,
                "FIELDS": [
                    "ID",
                    "WADMKK",
                    "KET_HA",
                    fld_pop,
                ],  # ← tambahkan WADMKK di sini
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Tambahkan SJEPGN, SJEBUILT, SJELHN
        step_sjepgn = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": base,
                "FIELD_NAME": "SJEPGN",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 6,
                "NEW_FIELD": True,
                "FORMULA": f"{sjepgn}",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        step_sjebuilt = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": step_sjepgn,
                "FIELD_NAME": "SJEBUILT",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 6,
                "NEW_FIELD": True,
                "FORMULA": f"{sjebuilt}",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        step_sjelhn = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": step_sjebuilt,
                "FIELD_NAME": "SJELHN",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 6,
                "NEW_FIELD": True,
                "FORMULA": 'coalesce("SJEPGN",0)+coalesce("SJEBUILT",0)',
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # KEB_HA:
        # - (POP=0) ⇒ KEB_HA = SJELHN
        # - (POP>0) ⇒ KEB_HA = SJELHN * POPGRIDYY
        step_keb = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": step_sjelhn,
                "FIELD_NAME": "KEB_HA",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 6,
                "NEW_FIELD": True,
                "FORMULA": (
                    f'CASE WHEN coalesce("{fld_pop}",0)=0 '
                    f'THEN coalesce("SJELHN",0) '
                    f'ELSE coalesce("SJELHN",0)*coalesce("{fld_pop}",0) END'
                ),
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # AB_POP = KET_HA / SJELHN (integer)
        step_ab = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": step_keb,
                "FIELD_NAME": "AB_POP",
                "FIELD_TYPE": 1,
                "FIELD_LENGTH": 10,
                "FIELD_PRECISION": 0,
                "NEW_FIELD": True,
                "FORMULA": 'to_int( case when coalesce("SJELHN",0)=0 '
                'then 0 else coalesce("KET_HA",0)/nullif("SJELHN",0) end )',
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # IKPLHN = KET_HA / KEB_HA
        step_ikp = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": step_ab,
                "FIELD_NAME": "IKPLHN",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 6,
                "NEW_FIELD": True,
                "FORMULA": 'case when coalesce("KEB_HA",0)=0 '
                'then 0 else coalesce("KET_HA",0)/nullif("KEB_HA",0) end',
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # KIKPLHN (teks)
        expr_kik = (
            "CASE WHEN \"IKPLHN\" = 0 THEN 'Tidak Dihitung' "
            'WHEN ("IKPLHN" > 0 AND "IKPLHN" <= 0.05) THEN \'Sangat Rendah\' '
            'WHEN ("IKPLHN" > 0.05 AND "IKPLHN" <= 1.0) THEN \'Rendah\' '
            'WHEN ("IKPLHN" > 1.0 AND "IKPLHN" <= 1.5) THEN \'Sedang\' '
            'WHEN ("IKPLHN" > 1.5 AND "IKPLHN" <= 2) THEN \'Tinggi\' '
            "WHEN (\"IKPLHN\" > 2) THEN 'Sangat Tinggi' "
            "ELSE 'Tidak Dihitung' END"
        )
        step_kik = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": step_ikp,
                "FIELD_NAME": "KIKPLHN",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 255,
                "FIELD_PRECISION": 0,
                "NEW_FIELD": True,
                "FORMULA": expr_kik,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # SIKPLHN (teks, 1..5 atau 'Tidak Dihitung')
        expr_sik = (
            "CASE WHEN \"IKPLHN\" = 0 THEN 'Tidak Dihitung' "
            'WHEN ("IKPLHN" > 0 AND "IKPLHN" <= 0.05) THEN \'1\' '
            'WHEN ("IKPLHN" > 0.05 AND "IKPLHN" <= 1.0) THEN \'2\' '
            'WHEN ("IKPLHN" > 1.0 AND "IKPLHN" <= 1.5) THEN \'3\' '
            'WHEN ("IKPLHN" > 1.5 AND "IKPLHN" <= 2) THEN \'4\' '
            "WHEN (\"IKPLHN\" > 2) THEN '5' "
            "ELSE 'Tidak Dihitung' END"
        )
        step_sik = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": step_kik,
                "FIELD_NAME": "SIKPLHN",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 32,
                "FIELD_PRECISION": 0,
                "NEW_FIELD": True,
                "FORMULA": expr_sik,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # D_POP (integer) = AB_POP - POPGRIDYY
        step_dpop = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": step_sik,
                "FIELD_NAME": "D_POP",
                "FIELD_TYPE": 1,
                "FIELD_LENGTH": 10,
                "FIELD_PRECISION": 0,
                "NEW_FIELD": True,
                "FORMULA": f"""
                    to_int( coalesce("AB_POP",0) - coalesce("{fld_pop}",0) )
                """,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # STATUSPGN (teks) dari D_POP
        expr_status = (
            "CASE WHEN coalesce(\"D_POP\",0) < 0 THEN 'Terlampaui' "
            "ELSE 'Belum Terlampaui' END"
        )
        step_status = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": step_dpop,
                "FIELD_NAME": "STATUSPGN",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 64,
                "FIELD_PRECISION": 0,
                "NEW_FIELD": True,
                "FORMULA": expr_status,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # ── Urutan & tipe kolom final
        # (pakai QVariant codes: String=10, Int=2, Real=6) ──
        mapping = [
            # name           type  len   prec  expr
            {
                "name": "ID",
                "type": 10,
                "length": 32,
                "precision": 0,
                "expression": 'to_string("ID")',
            },
            {
                "name": "WADMKK",
                "type": 10,
                "length": 255,
                "precision": 0,
                "expression": 'to_string("WADMKK")',
            },
            {
                "name": "KET_HA",
                "type": 6,
                "length": 20,
                "precision": 6,
                "expression": 'to_real("KET_HA")',
            },
            {
                "name": f"{fld_pop}",
                "type": 2,
                "length": 10,
                "precision": 0,
                "expression": f'to_int("{fld_pop}")',
            },
            {
                "name": "SJEPGN",
                "type": 6,
                "length": 20,
                "precision": 6,
                "expression": 'to_real("SJEPGN")',
            },
            {
                "name": "SJEBUILT",
                "type": 6,
                "length": 20,
                "precision": 6,
                "expression": 'to_real("SJEBUILT")',
            },
            {
                "name": "SJELHN",
                "type": 6,
                "length": 20,
                "precision": 6,
                "expression": 'to_real("SJELHN")',
            },
            {
                "name": "KEB_HA",
                "type": 6,
                "length": 20,
                "precision": 6,
                "expression": 'to_real("KEB_HA")',
            },
            {
                "name": "AB_POP",
                "type": 2,
                "length": 10,
                "precision": 0,
                "expression": 'to_int("AB_POP")',
            },
            {
                "name": "D_POP",
                "type": 2,
                "length": 10,
                "precision": 0,
                "expression": 'to_int("D_POP")',
            },
            {
                "name": "STATUSPGN",
                "type": 10,
                "length": 255,
                "precision": 0,
                "expression": 'to_string("STATUSPGN")',
            },
            {
                "name": "IKPLHN",
                "type": 6,
                "length": 20,
                "precision": 6,
                "expression": 'to_real("IKPLHN")',
            },
            {
                "name": "SIKPLHN",
                "type": 10,
                "length": 255,
                "precision": 0,
                "expression": 'to_string("SIKPLHN")',
            },
            {
                "name": "KIKPLHN",
                "type": 10,
                "length": 255,
                "precision": 0,
                "expression": 'to_string("KIKPLHN")',
            },
        ]

        final_ikp_sel = processing.run(
            "qgis:refactorfields",
            {
                "INPUT": step_status,
                "FIELDS_MAPPING": mapping,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # === Tulis kedua output ===
        # 1) Ketersediaan Lahan (poligon pra-grid)
        sink_ket, dest_ket = self.parameterAsSink(
            parameters,
            self.OUTPUT_KETER,
            context,
            ket_pol_out_2.fields(),
            ket_pol_out_2.wkbType(),
            ket_pol_out_2.sourceCrs(),
        )
        for f in ket_pol_out_2.getFeatures():
            sink_ket.addFeature(f)

        # 2) IKP Lahan (grid)
        sink_ikp, dest_ikp = self.parameterAsSink(
            parameters,
            self.OUTPUT_IKP,
            context,
            final_ikp_sel.fields(),
            final_ikp_sel.wkbType(),
            final_ikp_sel.sourceCrs(),
        )
        for f in final_ikp_sel.getFeatures():
            sink_ikp.addFeature(f)

        return {self.OUTPUT_KETER: dest_ket, self.OUTPUT_IKP: dest_ikp}
