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

# -*- coding: utf-8 -*-
import os
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


class JLHFoodSupplyAlgorithm(QgsProcessingAlgorithm):
    """
    02. Indeks Jasa Lingkungan Hidup (IJLH) – JLH Penyedia Pangan
    """

    # PARAMETER KEYS
    JLH = "PGN"
    TAHUN = "TAHUN"
    BENTUK_OUTPUT = "BENTUK_OUTPUT"
    BENTUK_OUTPUT_OPTIONS = ["Grid", "Poligon"]
    SKOR = "SKOR"
    SKOR_OPTIONS = ["Kabupaten/Kota", "Nasional"]
    PENUTUP_LAHAN = "PENUTUP_LAHAN"
    EKOREGION = "EKOREGION"
    GRID = "GRID"
    OUTPUT = "OUTPUT"

    # NON-PARAM
    DAFTAR_PULAU = [
        "Jawa",
        "Sumatera",
        "Kalimantan",
        "Sulawesi",
        "Bali–Nusra",
        "Maluku",
        "Papua",
    ]

    # BOBOT (D3TLH 2024)
    BOBOT_EK = 0.28
    BOBOT_VE = 0.12
    BOBOT_LC = 0.60

    def initAlgorithm(self, config):
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
                self.GRID,
                self.tr("Grid (wajib bila output Grid)"),
                [QgsProcessing.TypeVectorAnyGeometry],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("JLH Penyedia Pangan")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # Ambil layers
        pl_src = self.parameterAsSource(
            parameters, self.PENUTUP_LAHAN, context
        )
        # ekoregion_src = self.parameterAsSource(
        #     parameters, self.EKOREGION, context
        # )
        grid_vl = self.parameterAsVectorLayer(
            parameters, self.GRID, context
        )

        bentuk_output = self.BENTUK_OUTPUT_OPTIONS[
            self.parameterAsEnum(
                parameters, self.BENTUK_OUTPUT, context
            )
        ]
        skor_jlh = self.SKOR_OPTIONS[
            self.parameterAsEnum(parameters, self.SKOR, context)
        ]
        tahun = str(
            self.parameterAsInt(parameters, self.TAHUN, context)
        )

        # Validasi awal
        if bentuk_output == "Grid" and grid_vl is None:
            raise QgsProcessingException(
                self.tr(
                    'Layer GRID wajib diisi bila memilih output "Grid".'
                )
            )
        if (
            bentuk_output == "Grid"
            and grid_vl.fields().indexFromName("ID") == -1
        ):
            raise QgsProcessingException(
                self.tr('Layer GRID harus memiliki kolom "ID".')
            )

        idx_pulau = pl_src.fields().indexFromName("PULAU")
        if idx_pulau == -1:
            raise QgsProcessingException(
                self.tr(
                    'Layer Penutup Lahan harus memiliki kolom "PULAU".'
                )
            )

        pulau_data = pl_src.uniqueValues(idx_pulau)
        if not pulau_data:
            raise QgsProcessingException(
                self.tr('Kolom "PULAU" pada Penutup Lahan kosong.')
            )
        # if skor_jlh == "Kabupaten/Kota":
        #     if len(pulau_data) != 1:
        #         raise QgsProcessingException(
        #             self.tr(
        #                 'Skor "Kabupaten/Kota" harus satu pulau per proses.'
        #             )
        #         )
        #     if any(p not in self.DAFTAR_PULAU for p in pulau_data):
        #         raise QgsProcessingException(
        #             self.tr(
        #                 "Pulau harus salah satu: "
        #                 f'{", ".join(self.DAFTAR_PULAU)}'
        #             )
        #         )
        #     selected_pulau = list(pulau_data)[0]
        # else:
        #     selected_pulau = list(pulau_data)[0]  # PERUBAHAN

        # Lokasi data skor
        this_file = os.path.abspath(__file__)
        plugin_root = os.path.dirname(
            os.path.dirname(os.path.dirname(this_file))
        )
        data_root = os.path.join(
            plugin_root, "data", f"jlh_{self.JLH.lower()}"
        )
        data_root_kabkota = os.path.join(data_root, "kabupaten_kota")

        # Helper
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
            # Capitalize properly (one word or two word with hyphen)
            island_name = island_name.title()
            base = {
                "Jawa": "skor_pl_pgn_jawa.csv",
                "Sumatera": "skor_pl_pgn_sumatera.csv",
                "Kalimantan": "skor_pl_pgn_kalimantan.csv",
                "Sulawesi": "skor_pl_pgn_sulawesi.csv",
                "Papua": "skor_pl_pgn_papua.csv",
                "Bali-Nusra": "skor_pl_pgn_balinusra.csv",
                "Maluku": "skor_pl_pgn_maluku.csv",
            }
            return base[island_name]

        # 1) Intersection PL × Ekoregion (bawa PULAU, PL, KBA_250, KVA_250)
        inter = processing.run(
            "qgis:intersection",
            {
                "INPUT": parameters[self.PENUTUP_LAHAN],
                "OVERLAY": parameters[self.EKOREGION],
                "INPUT_FIELDS": ["PULAU", "PL"],
                "OVERLAY_FIELDS": ["KBA_250", "KVA_250"],
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # 2) Join Skor KBA
        kba_layer = load_csv_table(
            os.path.join(data_root, f"skor_kba_{self.JLH.lower()}.csv"),
            f"skor_kba_{self.JLH.lower()}",
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
        kva_layer = load_csv_table(
            os.path.join(data_root, f"skor_kva_{self.JLH.lower()}.csv"),
            f"skor_kva_{self.JLH.lower()}",
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

        # 4) JOIN SKOR PENUTUP LAHAN
        def join_skor_pl_once(source_layer):
            current = source_layer

            # Dapatkan daftar unik pulau dari layer input
            pulau_values = set(
                [
                    f["PULAU"]
                    for f in current.getFeatures()
                    if f["PULAU"]
                ]
            )

            for pulau in pulau_values:
                pulau_lower = pulau.lower()

                # Tentukan path file
                if skor_jlh == "Kabupaten/Kota":
                    csv_path = os.path.join(
                        data_root_kabkota, pl_filename(pulau)
                    )
                    name = f"skor_pl_{self.JLH.lower()}_{pulau_lower}"
                elif skor_jlh == "Nasional":
                    csv_path = os.path.join(
                        data_root, pl_filename(pulau)
                    )
                    name = f"skor_pl_{self.JLH.lower()}_{pulau_lower}"
                else:
                    raise ValueError(
                        f"Tipe skor tidak dikenali: {skor_jlh}"
                    )

                feedback.pushInfo(
                    f"Joining skor for pulau {pulau} → {csv_path}"
                )

                # Load CSV
                pl_layer = load_csv_table(csv_path, name)

                # Join berdasarkan PL
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

                # Rename joined field supaya unik (misalnya S_PL_sumatera)
                field_name = f"S_PL_{pulau_lower}"
                current = processing.run(
                    "qgis:refactorfields",
                    {
                        "INPUT": current,
                        "FIELDS_MAPPING": [
                            {
                                "expression": '"S_PL"',
                                "name": field_name,
                                "type": 2,
                                "length": 10,
                                "precision": 0,
                            }
                        ]
                        + [
                            {
                                "expression": f'"{fld.name()}"',
                                "name": fld.name(),
                                "type": fld.type(),
                                "length": fld.length(),
                                "precision": fld.precision(),
                            }
                            for fld in current.fields()
                            if fld.name() != "S_PL"
                        ],
                        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                    },
                    context=context,
                    feedback=feedback,
                )["OUTPUT"]

            # Setelah semua join selesai → buat S_PL tunggal pakai CASE
            case_expr = (
                "CASE "
                + " ".join(
                    [
                        f'WHEN "PULAU" = \'{p}\' THEN "S_PL_{p.lower()}"'
                        for p in pulau_values
                    ]
                )
                + " ELSE NULL END"
            )

            current = processing.run(
                "qgis:fieldcalculator",
                {
                    "INPUT": current,
                    "FIELD_NAME": "S_PL",
                    "FIELD_TYPE": 0,  # float
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 2,
                    "NEW_FIELD": True,
                    "FORMULA": case_expr,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            return current

        src_pl = join_skor_pl_once(src_kva)

        feedback.pushInfo(f"Selesai join skor PL ({skor_jlh})")

        # 5) Hitung indeks
        src_idx = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": src_pl,
                "FIELD_NAME": f"JLH_{self.JLH}",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 2,
                "NEW_FIELD": True,
                "FORMULA": f"""
                    "S_EK"*{self.BOBOT_EK}
                    + "S_VE"*{self.BOBOT_VE}
                    + "S_PL"*{self.BOBOT_LC}
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # 6) Bentuk output
        if bentuk_output == "Poligon":
            out_src = src_idx
        else:
            # === GRID (agregasi tabular, stabil) ===
            inter_grid = processing.run(
                "qgis:intersection",
                {
                    "INPUT": src_idx,
                    "OVERLAY": parameters[self.GRID],
                    "INPUT_FIELDS": ["PULAU", f"JLH_{self.JLH}"],
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
            area_by_id = processing.run(
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

            inter_with_ag = processing.run(
                "qgis:joinattributestable",
                {
                    "INPUT": area_poly,
                    "FIELD": "ID",
                    "INPUT_2": area_by_id,
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
                    "INPUT": inter_with_ag,
                    "FIELD_NAME": "JLH_PROP",
                    "FIELD_TYPE": 0,
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 6,
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
                    "VALUES_FIELD_NAME": "JLH_PROP",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            # Ambil PULAU per-ID (sertakan ID di output aggregate
            # supaya join valid)
            pulau_per_id = processing.run(
                "qgis:aggregate",
                {
                    "INPUT": prop,
                    "GROUP_BY": "ID",
                    "AGGREGATES": [
                        {
                            "aggregate": "first_value",
                            "delimiter": ",",
                            "input": '"ID"',
                            "length": 0,
                            "name": "ID",
                            "precision": 0,
                            "type": 10,
                        },
                        {
                            "aggregate": "first_value",
                            "delimiter": ",",
                            "input": '"PULAU"',
                            "length": 80,
                            "name": "PULAU",
                            "precision": 0,
                            "type": 10,
                        },
                    ],
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            grid_join_val = processing.run(
                "qgis:joinattributestable",
                {
                    "INPUT": parameters[self.GRID],
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
            grid_join_val = processing.run(
                "qgis:renametablefield",
                {
                    "INPUT": grid_join_val,
                    "FIELD": "sum",
                    "NEW_NAME": f"JLH_{self.JLH}",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            grid_with_pulau = processing.run(
                "qgis:joinattributestable",
                {
                    "INPUT": grid_join_val,
                    "FIELD": "ID",
                    "INPUT_2": pulau_per_id,
                    "FIELD_2": "ID",
                    "FIELDS_TO_COPY": ["PULAU"],
                    "METHOD": 0,
                    "DISCARD_NONMATCHING": False,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            out_src = grid_with_pulau
            # === END GRID ==

        # 8) Kolom kategori
        out_src = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": out_src,
                "FIELD_NAME": f"Kategori_JLH_{self.JLH}",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 20,
                "NEW_FIELD": True,
                "FORMULA": f"""
                CASE
                    WHEN "JLH_{self.JLH}" >= 1.0 AND "JLH_{self.JLH}"
                        <= 1.8 THEN 'Sangat Rendah'
                    WHEN "JLH_{self.JLH}" > 1.8 AND "JLH_{self.JLH}"
                        <= 2.6 THEN 'Rendah'
                    WHEN "JLH_{self.JLH}" > 2.6 AND "JLH_{self.JLH}"
                        <= 3.4 THEN 'Sedang'
                    WHEN "JLH_{self.JLH}" > 3.4 AND "JLH_{self.JLH}"
                        <= 4.2 THEN 'Tinggi'
                    WHEN "JLH_{self.JLH}" > 4.2 AND "JLH_{self.JLH}"
                        <= 5.0 THEN 'Sangat Tinggi'
                    ELSE 'Tidak Diketahui'
                END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # 9) Standarisasi Nama-Nama Kolom
        final_field_mappings = build_field_mappings_jlh(
            jlh=self.JLH,
            tahun=tahun,
            bentuk_output=self.BENTUK_OUTPUT,
            layer=out_src,
        )

        out_src = processing.run(
            "qgis:refactorfields",
            {
                "INPUT": out_src,
                "FIELDS_MAPPING": final_field_mappings,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        feedback.pushInfo(
            "✅ Standarisasi nama-nama kolom output berhasil"
        )

        # Output sink
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
        for current, feat in enumerate(out_src.getFeatures()):
            if feedback.isCanceled():
                break
            sink.addFeature(feat, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}

    # Metadata
    def name(self):
        return "JLH Penyedia Pangan"

    def displayName(self):
        return self.tr(self.name())

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return "C. Indeks Jasa Lingkungan Hidup (IJLH)"

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(__file__), "03 Ecosystem Services.svg"
            )
        )

    def shortHelString(self):
        return self.tr('<b>Docs read <a href="#">here</a>.<b>')

    def shortHelpString(self):
        return self.tr(
            "This algorithm calculates the Food Provision Ecosystem "
            "Service Index (JLH_PGN), which represents an ecosystem's "
            "capacity to provide food resources from both natural "
            "ecosystems and cultivated production systems.\n\n"
            "The methodology follows the D3TLH Technical Guideline 2024 "
            "and has been adapted to Indonesia's ecological and "
            "ecoregional conditions for analysis at both national and "
            "island scales.\n\n"
            "<b>Complete explanation read here: "
            "<a href='https://yayasan-lokahita.github.io/"
            "otomatisasi_d3tlh-docs/jlh/jlh_pgn/'>here</a>.</b>"
        )

    def createInstance(self):
        return JLHFoodSupplyAlgorithm()
