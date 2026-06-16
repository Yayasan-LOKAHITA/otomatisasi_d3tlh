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

import os
import re
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsFeatureSink,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsVectorLayer,
    QgsProcessingException,
)
import processing
from ..core.field_mappings import build_field_mappings_jlh
from qgis.PyQt.QtGui import QIcon


class JLHHabitatKehatiAlgorithm(QgsProcessingAlgorithm):
    """
    02. Indeks Jasa Lingkungan Hidup (IJLH) – JLH Pendukung Habitat dan Kehati
    """

    # VARIABEL PARAMETER INPUT DAN OUTPUT.
    JLH = "PHK"
    TAHUN = "TAHUN"
    BENTUK_OUTPUT = "BENTUK_OUTPUT"
    BENTUK_OUTPUT_OPTIONS = ["Grid", "Poligon"]
    SKOR = "SKOR"
    SKOR_OPTIONS = ["Kabupaten/Kota", "Nasional"]
    PENUTUP_LAHAN = "PENUTUP_LAHAN"
    EKOREGION = "EKOREGION"
    KK = "KK"
    GRID = "GRID"
    OUTPUT = "OUTPUT"

    # VARIABEL KONTROL NON PARAMETER
    # DAFTAR PULAU UNTUK LOAD SKOR KABUPATEN/KOTA
    DAFTAR_PULAU = [
        "Jawa",
        "Sumatera",
        "Kalimantan",
        "Sulawesi",
        "Bali–Nusra",
        "Maluku",
        "Papua",
    ]

    # BOBOT KONTRIBUSI TIAP VARIABEL
    # SUMBER: Dokumen D3TLH 2024
    BOBOT_EK = 0.24
    BOBOT_VE = 0.16
    BOBOT_LC = 0.60

    def initAlgorithm(self, config):
        # PARAMETER INPUT DAN OUTPUT
        self.addParameter(
            QgsProcessingParameterEnum(
                self.BENTUK_OUTPUT,
                self.tr("Bentuk Output"),
                options=self.BENTUK_OUTPUT_OPTIONS,
                defaultValue=1,  # Poligon
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.SKOR,
                self.tr("Skor IJLH yang Digunakan"),
                options=self.SKOR_OPTIONS,
                defaultValue=1,  # Nasional
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TAHUN,
                "Tahun Data Penutup Lahan (Contoh: 2024)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=2024,
                minValue=2000,
                maxValue=2100,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.PENUTUP_LAHAN,
                self.tr("Penutup Lahan"),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.EKOREGION,
                self.tr("Ekoregion"),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.KK,
                self.tr("KK (Kriteria Khusus)"),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.GRID,
                self.tr("Grid (wajib bila output Grid)"),
                [QgsProcessing.TypeVectorAnyGeometry],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("JLH Pendukung Habitat dan Kehati")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # LAYER INPUT
        pl = parameters[self.PENUTUP_LAHAN]
        ekoregion = parameters[self.EKOREGION]
        kk = parameters[self.KK]
        grid = parameters[self.GRID]

        # LAYER INPUT SEBAGAI QgsVectorLayer
        pl_src = self.parameterAsSource(
            parameters, self.PENUTUP_LAHAN, context
        )
        # ekoregion_src = self.parameterAsSource(
        #     parameters, self.EKOREGION, context
        # )
        # kk_src = self.parameterAsSource(parameters, self.KK, context)
        grid_src = self.parameterAsVectorLayer(
            parameters, self.GRID, context
        )

        # PARAMETER INPUT
        bentuk_output = self.BENTUK_OUTPUT_OPTIONS[
            self.parameterAsEnum(
                parameters, self.BENTUK_OUTPUT, context
            )
        ]
        skor_jlh = self.SKOR_OPTIONS[
            self.parameterAsEnum(parameters, self.SKOR, context)
        ]
        tahun = self.parameterAsString(parameters, self.TAHUN, context)

        # PENGECEKAN INPUT DATA
        if bentuk_output == "Grid" and grid_src is None:
            raise QgsProcessingException(
                self.tr(
                    'Layer GRID wajib diisi bila memilih output "Grid".'
                )
            )

        # IDENTIFIKASI PULAU DARI DATA YANG SEDANG DIANALISIS
        pulau_data = pl_src.uniqueValues(
            pl_src.fields().indexFromName("PULAU")
        )

        # PENGECEKAN KOLOM PULAU DI LAYER PENUTUP LAHAN
        if pulau_data is None or len(pulau_data) == 0:
            raise QgsProcessingException(
                self.tr(
                    'Layer Penutup Lahan harus memiliki kolom "PULAU" '
                    "yang terisi."
                )
            )

        # PENGECEKAN KONSISTENSI PULAU DENGAN SKOR IJLH YANG DIPILIH
        elif skor_jlh == "Kabupaten/Kota" and len(pulau_data) == 0:
            raise QgsProcessingException(
                self.tr(
                    'Untuk Skor IJLH "Kabupaten/Kota", layer Penutup Lahan '
                    'harus memiliki kolom "PULAU" yang terisi.'
                )
            )
        elif skor_jlh == "Kabupaten/Kota" and len(pulau_data) > 1:
            raise QgsProcessingException(
                self.tr(
                    'Untuk Skor IJLH "Kabupaten/Kota", layer Penutup Lahan '
                    "harus hanya berisi satu pulau."
                )
            )
        elif skor_jlh == "Kabupaten/Kota" and any(
            p not in self.DAFTAR_PULAU for p in pulau_data
        ):
            raise QgsProcessingException(
                self.tr(
                    f"Pulau pada layer Penutup Lahan harus salah satu dari: "
                    f'{", ".join(self.DAFTAR_PULAU)}'
                )
            )

        selected_pulau = [
            p for p in pulau_data if p in self.DAFTAR_PULAU
        ]

        # FOLDER PATH DATA
        this_file = os.path.abspath(__file__)
        plugin_root = os.path.dirname(
            os.path.dirname(os.path.dirname(this_file))
        )
        data_root = os.path.join(
            plugin_root, "data", f"jlh_{self.JLH.lower()}"
        )
        data_root_kabkota = os.path.join(data_root, "kabupaten_kota")

        # HELPER FUNCTIONS : load_csv_table, pl_filename, sanitize_suffix,
        # has_field
        def load_csv_table(
            csv_abs_path: str, name: str
        ) -> QgsVectorLayer:
            csv_abs_path = os.path.normpath(csv_abs_path)

            for delim in (";", ","):
                uri = (
                    f"file:///{csv_abs_path}"
                    f"?encoding=UTF-8"
                    f"&delimiter={delim}"
                    f"&geomType=none"
                )

                layer = QgsVectorLayer(uri, name, "delimitedtext")

                if layer.isValid() and len(layer.fields()) > 1:
                    return layer

            raise QgsProcessingException(
                self.tr(
                    f"CSV tidak valid/tidak ditemukan:\n{csv_abs_path}"
                )
            )

        def pl_filename(island_name: str) -> str:
            base = {
                "Jawa": f"skor_pl_{self.JLH.lower()}_jawa.csv",
                "Sumatera": f"skor_pl_{self.JLH.lower()}_sumatera.csv",
                "Kalimantan": f"skor_pl_{self.JLH.lower()}_kalimantan.csv",
                "Sulawesi": f"skor_pl_{self.JLH.lower()}_sulawesi.csv",
                "Papua": f"skor_pl_{self.JLH.lower()}_papua.csv",
                "Bali–Nusra": f"skor_pl_{self.JLH.lower()}_balinusra.csv",
                "Maluku": f"skor_pl_{self.JLH.lower()}_maluku.csv",
            }
            return base[island_name]

        def sanitize_suffix(s: str) -> str:
            # buat nama kolom aman, contoh "Bali–Nusra" -> "BaliNusra"
            return re.sub(r"[^A-Za-z0-9]+", "", s)

        def has_field(layer: QgsVectorLayer, name: str) -> bool:
            return layer.fields().indexFromName(name) != -1

        # --- PROSES ANALISIS ---
        # 1) Intersection PL × Ekoregion (bawa LC, KBA_250, KVA_250, dan PULAU)
        inter = processing.run(
            "qgis:intersection",
            {
                "INPUT": pl,
                "OVERLAY": ekoregion,
                "INPUT_FIELDS": ["PULAU", "PL"],
                "OVERLAY_FIELDS": ["KBA_250", "KVA_250"],
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        feedback.pushInfo(
            f"✅ Intersection antara Penutup Lahan dan Ekoregion berhasil, "
            f"total fitur: {inter.featureCount()}"
        )

        # 2) Join Skor KBA
        kba_csv = os.path.join(
            data_root, f"skor_kba_{self.JLH.lower()}.csv"
        )
        kba_layer = load_csv_table(
            kba_csv, f"skor_kba_{self.JLH.lower()}"
        )
        src_kba = processing.run(
            "qgis:joinattributestable",
            {
                "INPUT": inter,
                "FIELD": "KBA_250",
                "INPUT_2": kba_layer,
                "FIELD_2": "EKOREGION",
                "FIELDS_TO_COPY": ["S_EK"],
                "METHOD": 0,
                "DISCARD_NONMATCHING": False,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # 3) Join Skor KVA
        kva_csv = os.path.join(
            data_root, f"skor_kva_{self.JLH.lower()}.csv"
        )
        kva_layer = load_csv_table(
            kva_csv, f"skor_kva_{self.JLH.lower()}"
        )
        src_kva = processing.run(
            "qgis:joinattributestable",
            {
                "INPUT": src_kba,
                "FIELD": "KVA_250",
                "INPUT_2": kva_layer,
                "FIELD_2": "VEGETASI",
                "FIELDS_TO_COPY": ["S_VE"],
                "METHOD": 0,
                "DISCARD_NONMATCHING": False,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # 4) Join PL
        def join_skor_pl(source_layer):
            current = source_layer

            if skor_jlh == "Kabupaten/Kota":
                # Mode KABUPATEN/KOTA: hanya join satu pulau yang ada di data
                pulau = selected_pulau[0]
                csv_path = os.path.join(
                    data_root_kabkota, pl_filename(pulau)
                )
                name = f"skor_pl_{pulau.lower()}"
                pl_layer = load_csv_table(csv_path, name)

                # join berdasarkan PL → copy S_PL_KABKOTA lalu
                # normalisasi ke S_LC
                current = processing.run(
                    "qgis:joinattributestable",
                    {
                        "INPUT": current,
                        "FIELD": "PL",
                        "INPUT_2": pl_layer,
                        "FIELD_2": "PL",
                        "FIELDS_TO_COPY": ["S_PL"],
                        "METHOD": 0,
                        "DISCARD_NONMATCHING": False,
                        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                    },
                    context=context,
                    feedback=feedback,
                )["OUTPUT"]

                return current

            # —— Mode NASIONAL: join per-pulau → hasilkan kolom S_PL_<Pulau>,
            # lalu pilih pakai kolom PULAU
            else:
                csv_path = os.path.join(
                    data_root, f"skor_pl_{self.JLH.lower()}.csv"
                )  # Skor PL tidak per Pulau
                name = f"skor_pl_{self.JLH.lower()}"
                pl_layer = load_csv_table(csv_path, name)

                # join berdasarkan PL → copy S_PL
                current = processing.run(
                    "qgis:joinattributestable",
                    {
                        "INPUT": current,
                        "FIELD": "PL",
                        "INPUT_2": pl_layer,
                        "FIELD_2": "PL",
                        "FIELDS_TO_COPY": ["S_PL"],
                        "METHOD": 0,
                        "DISCARD_NONMATCHING": False,
                        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                    },
                    context=context,
                    feedback=feedback,
                )["OUTPUT"]

                return current

        src_pl = join_skor_pl(src_kva)
        feedback.pushInfo(f"✅ Selesai join skor PL ({skor_jlh})")

        # 5) Hitung indeks
        src_idx = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": src_pl,
                "FIELD_NAME": f"JLH_{self.JLH}",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 3,
                "FIELD_PRECISION": 2,
                "NEW_FIELD": True,
                "FORMULA": f"""
                    ("S_EK"*{self.BOBOT_EK} + "S_VE"*{self.BOBOT_VE} +
                    "S_PL"*{self.BOBOT_LC})
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        feedback.pushInfo("✅ Perhitungan JLH Kehati berhasil")

        # 6) Bentuk output
        if bentuk_output == "Poligon":
            # 0. Load dan clip KK sesuai data input
            clip_kk = processing.run(
                "qgis:clip",
                {
                    "INPUT": kk,
                    "OVERLAY": src_idx,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            # 1. Intersection dengan merged_layer (KK + kriteria khusus)
            union_params = {
                "INPUT": src_idx,
                "OVERLAY": clip_kk,
                "INPUT_FIELDS": [],
                "OVERLAY_FIELDS": ["KK"],
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            }
            union = processing.run(
                "qgis:union",
                union_params,
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            filter_feature = processing.run(
                "qgis:extractbyexpression",
                {
                    "INPUT": union,
                    "EXPRESSION": """
                        NOT ("KBA_250" IS NULL
                            AND "KVA_250" IS NULL
                            AND "PL" IS NULL
                        )
                    """,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            feedback.pushInfo(
                f"✅ Union dengan layer KK khusus berhasil, total fitur: "
                f"{union.featureCount()}"
            )

            # 2. Override (Membuat skor menjadi auto 5) JLH_Kehati sesuai
            # rules (KK, Savana, Tubuh Air)
            override_formula = f"""
            CASE
                WHEN "KK" = 1 THEN 5
                WHEN "PL" = 'Savana/Padang Rumput'
                    AND "KODE_PROV" IN (51,52,53,91,92,94,95,96) THEN 5
                WHEN "PL" IN ('Tubuh Air','Badan Air') THEN 5
                ELSE "JLH_{self.JLH}"
            END
            """
            override_params = {
                "INPUT": filter_feature,
                "FIELD_NAME": f"JLH_{self.JLH}_KK",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 3,
                "FIELD_PRECISION": 2,
                "NEW_FIELD": True,
                "FORMULA": override_formula,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            }
            source_final = processing.run(
                "qgis:fieldcalculator",
                override_params,
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            out_src3 = source_final
            feedback.pushInfo(
                "✅ Semua kriteria override (KK, Savana, Tubuh Air) "
                "berhasil diterapkan"
            )

        elif bentuk_output == "Grid":
            # LOAD LAYER MCA GRID PL Untuk Kriteria Khusus Bentuk Output Grid
            mca_pl = processing.run(
                "d3tlh:mcagrid",
                {
                    "GRID": grid,
                    "LAYER2": pl,
                    "LAYER2_FIELD": "PL",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            inter_grid = processing.run(
                "qgis:intersection",
                {
                    "INPUT": src_idx,
                    "OVERLAY": grid,
                    "INPUT_FIELDS": [],
                    "OVERLAY_FIELDS": ["ID"],
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            area_poly = processing.run(
                "qgis:fieldcalculator",
                {
                    "INPUT": inter_grid,
                    "FIELD_NAME": "AREA_POLY_M2",
                    "FIELD_TYPE": 0,
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 3,
                    "NEW_FIELD": True,
                    "FORMULA": "$area",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            area_by_id = processing.run(
                "qgis:statisticsbycategories",
                {
                    "INPUT": area_poly,
                    "CATEGORIES_FIELD_NAME": ["ID"],
                    "VALUES_FIELD_NAME": "AREA_POLY_M2",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            area_by_id_renamed = processing.run(
                "qgis:renametablefield",
                {
                    "INPUT": area_by_id,
                    "FIELD": "sum",
                    "NEW_NAME": "AREA_GRID_M2",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            inter_grid_with_area = processing.run(
                "qgis:joinattributestable",
                {
                    "INPUT": area_poly,
                    "FIELD": "ID",
                    "INPUT_2": area_by_id_renamed,
                    "FIELD_2": "ID",
                    "FIELDS_TO_COPY": ["AREA_GRID_M2"],
                    "METHOD": 0,
                    "DISCARD_NONMATCHING": False,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            prop = processing.run(
                "qgis:fieldcalculator",
                {
                    "INPUT": inter_grid_with_area,
                    "FIELD_NAME": "JLH_Kehati_Proporsional",
                    "FIELD_TYPE": 0,
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 3,
                    "NEW_FIELD": True,
                    "FORMULA": f"""
                        "JLH_{self.JLH}" * ("AREA_POLY_M2" / "AREA_GRID_M2")
                    """,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            summed = processing.run(
                "qgis:statisticsbycategories",
                {
                    "INPUT": prop,
                    "CATEGORIES_FIELD_NAME": ["ID"],
                    "VALUES_FIELD_NAME": "JLH_Kehati_Proporsional",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            grid_join = processing.run(
                "qgis:joinattributestable",
                {
                    "INPUT": grid,
                    "FIELD": "ID",
                    "INPUT_2": summed,
                    "FIELD_2": "ID",
                    "FIELDS_TO_COPY": ["sum"],
                    "METHOD": 0,
                    "DISCARD_NONMATCHING": False,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            out_srct3 = processing.run(
                "qgis:renametablefield",
                {
                    "INPUT": grid_join,
                    "FIELD": "sum",
                    "NEW_NAME": f"JLH_{self.JLH}",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            feedback.pushInfo(
                f"✅ Pembentukan grid JLH Kehati berhasil, total fitur: "
                f"{out_srct3.featureCount()}"
            )

            # KRITERIA KHUSUS
            select_src = processing.run(
                "qgis:extractbylocation",
                {
                    "INPUT": out_srct3,
                    "PREDICATE": [0],  # intersect
                    "INTERSECT": kk,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            # override skor JLH di fitur yang terpilih
            select_src = processing.run(
                "qgis:fieldcalculator",
                {
                    "INPUT": select_src,
                    "FIELD_NAME": f"JLH_{self.JLH}_KK",
                    "FIELD_TYPE": 0,
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 3,
                    "NEW_FIELD": False,
                    "FORMULA": "5",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            # gabungkan kembali dengan fitur yang tidak terpilih
            out_srct2 = processing.run(
                "qgis:joinattributestable",
                {
                    "INPUT": out_srct3,
                    "FIELD": "ID",
                    "INPUT_2": select_src,
                    "FIELD_2": "ID",
                    "FIELDS_TO_COPY": [f"JLH_{self.JLH}_KK"],
                    # take attributes of the first matching
                    # feature only (one-to-one)
                    "METHOD": 1,
                    "DISCARD_NONMATCHING": False,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]
            # apply override skor JLH
            out_srct1 = processing.run(
                "qgis:fieldcalculator",
                {
                    "INPUT": out_srct2,
                    "FIELD_NAME": f"JLH_{self.JLH}_KK",
                    "FIELD_TYPE": 0,
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 3,
                    "NEW_FIELD": False,
                    "FORMULA": f"""
                        coalesce("JLH_{self.JLH}_KK", "JLH_{self.JLH}")
                    """,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            feedback.pushInfo(
                "✅ Penerapan kriteria khusus poligon KK pada grid "
                "JLH Kehati berhasil"
            )

            # Apply kriteria khusus lainnya (Savana, Tubuh Air)

            # join mca_pl ke out_src
            out_srct = processing.run(
                "qgis:joinattributestable",
                {
                    "INPUT": out_srct1,
                    "FIELD": "ID",
                    "INPUT_2": mca_pl,
                    "FIELD_2": "ID",
                    "FIELDS_TO_COPY": ["PL"],
                    # take attributes of the first matching
                    # feature only (one-to-one)
                    "METHOD": 1,
                    "DISCARD_NONMATCHING": False,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            # apply kriteria khusus Savana dan Tubuh Air
            override_formula = f"""
            CASE
                WHEN "PL" = 'Savana/Padang Rumput'
                    AND "KODE_PROV" IN (51,52,53,91,92,94,95,96) THEN 5
                WHEN "PL" IN ('Tubuh Air','Badan Air') THEN 5
                ELSE "JLH_{self.JLH}"
            END
            """
            override_params = {
                "INPUT": out_srct,
                "FIELD_NAME": f"JLH_{self.JLH}_KK",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 3,
                "NEW_FIELD": False,
                "FORMULA": override_formula,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            }
            out_src3 = processing.run(
                "qgis:fieldcalculator",
                override_params,
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            feedback.pushInfo(
                "✅ Penerapan kriteria khusus Savana dan Tubuh Air pada "
                "grid JLH Kehati berhasil"
            )

        # 8) Kolom kategori
        out_src2 = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": out_src3,
                "FIELD_NAME": f"Kategori_JLH_{self.JLH}",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 20,
                "NEW_FIELD": True,
                "FORMULA": f"""
                    CASE
                        WHEN "JLH_{self.JLH}" <= 1.8
                            THEN 'Sangat Rendah'

                        WHEN "JLH_{self.JLH}" <= 2.6
                            THEN 'Rendah'

                        WHEN "JLH_{self.JLH}" <= 3.4
                            THEN 'Sedang'

                        WHEN "JLH_{self.JLH}" <= 4.2
                            THEN 'Tinggi'

                        WHEN "JLH_{self.JLH}" <= 5.0
                            THEN 'Sangat Tinggi'

                        ELSE 'Tidak Diketahui'
                    END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback.pushInfo(
                "✅ Pembuatan kolom kategori JLH Kehati berhasil"
            ),
        )["OUTPUT"]

        out_src1 = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": out_src2,
                "FIELD_NAME": f"Kategori_JLH_{self.JLH}_KK",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 20,
                "NEW_FIELD": True,
                "FORMULA": f"""
                    CASE
                        WHEN "JLH_{self.JLH}_KK" < 1.0
                            THEN 'Tidak Diketahui'

                        WHEN "JLH_{self.JLH}_KK" <= 1.8
                            THEN 'Sangat Rendah'

                        WHEN "JLH_{self.JLH}_KK" <= 2.6
                            THEN 'Rendah'

                        WHEN "JLH_{self.JLH}_KK" <= 3.4
                            THEN 'Sedang'

                        WHEN "JLH_{self.JLH}_KK" <= 4.2
                            THEN 'Tinggi'

                        WHEN "JLH_{self.JLH}_KK" <= 5.0
                            THEN 'Sangat Tinggi'

                        ELSE 'Tidak Diketahui'
                    END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback.pushInfo(
                "✅ Pembuatan kolom kategori JLH Kehati Kriteria"
                "Khusus berhasil"
            ),
        )["OUTPUT"]

        # 9) Standarisasi Nama-Nama Kolom
        final_field_mappings = build_field_mappings_jlh(
            jlh=self.JLH,
            tahun=tahun,
            bentuk_output=self.BENTUK_OUTPUT,
            layer=out_src1,
        )

        out_src = processing.run(
            "qgis:refactorfields",
            {
                "INPUT": out_src1,
                "FIELDS_MAPPING": final_field_mappings,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        feedback.pushInfo(
            "✅ Standarisasi nama-nama kolom output berhasil"
        )

        # --- Buat feature sink untuk output akhir ---
        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_src.fields(),
            out_src.wkbType(),
            out_src.sourceCrs(),
        )

        total = (
            100.0 / out_src.featureCount()
            if out_src.featureCount()
            else 0
        )
        for current, feature in enumerate(out_src.getFeatures()):
            if feedback.isCanceled():
                break
            sink.addFeature(feature, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(current * total))

        feedback.pushInfo(self.tr("Selesai."))

        return {self.OUTPUT: dest_id}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "JLH Pendukung Habitat dan Kehati"

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "C. Indeks Jasa Lingkungan Hidup (IJLH)"

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(__file__), "03 Ecosystem Services.svg"
            )
        )

    def shortHelpString(self):
        return self.tr(
            "This algorithm is used to calculate the Habitat and "
            "Biodiversity Supporting Ecosystem Service Index (IJLH_PHK) "
            "based on specific spatial parameters in Indonesia.\n\n"
            "The methodology is based on the D3TLH Technical Guideline "
            "2024 and has been adapted to support spatial analysis at both "
            "national and island scales.\n\n"
            "<b>Complete explanation read here: "
            "<a href='https://yayasan-lokahita.github.io/"
            "otomatisasi_d3tlh-docs/jlh/jlh_phk/'>here</a>.</b>"
        )

    def createInstance(self):
        return JLHHabitatKehatiAlgorithm()
