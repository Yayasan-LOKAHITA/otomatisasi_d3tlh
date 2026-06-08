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


class JLHWaterRegulationAlgorithm(QgsProcessingAlgorithm):
    """
    02. Indeks Jasa Lingkungan Hidup (IJLH) – JLH Pengaturan Air
    """

    # VARIABEL PARAMETER INPUT DAN OUTPUT.
    JLH = "PGA"
    TAHUN = "TAHUN"
    BENTUK_OUTPUT = "BENTUK_OUTPUT"
    BENTUK_OUTPUT_OPTIONS = ["Grid", "Poligon"]
    SKOR = "SKOR"
    SKOR_OPTIONS = ["Kabupaten/Kota", "Nasional"]
    PENUTUP_LAHAN = "PENUTUP_LAHAN"
    EKOREGION = "EKOREGION"
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
    BOBOT_EK = 0.28
    BOBOT_VE = 0.12
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
                self.GRID,
                self.tr("Grid (wajib bila output Grid)"),
                [QgsProcessing.TypeVectorAnyGeometry],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("JLH Pengaturan Air")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # LAYER INPUT
        pl = parameters[self.PENUTUP_LAHAN]
        ekoregion = parameters[self.EKOREGION]
        grid = parameters[self.GRID]

        # LAYER INPUT SEBAGAI QgsVectorLayer
        pl_src = self.parameterAsSource(
            parameters, self.PENUTUP_LAHAN, context
        )
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
        elif len(pulau_data) > 1 and skor_jlh == "Kabupaten/Kota":
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
                uri = f"""
                    file:///{csv_abs_path}?encoding=UTF-8&delimiter=
                    {delim}&geomType=none
                """
                lyr = QgsVectorLayer(uri, name, "delimitedtext")
                if lyr.isValid():
                    return lyr
            raise QgsProcessingException(
                self.tr(
                    f"CSV tidak valid atau tidak ditemukan:\n{csv_abs_path}"
                )
            )

        def pl_filename(island_name: str) -> str:
            base = {
                "Jawa": "skor_pl_pga_jawa.csv",
                "Sumatera": "skor_pl_pga_sumatera.csv",
                "Kalimantan": "skor_pl_pga_kalimantan.csv",
                "Sulawesi": "skor_pl_pga_sulawesi.csv",
                "Papua": "skor_pl_pga_papua.csv",
                "Bali–Nusra": "skor_pl_pga_balinusra.csv",
                "Maluku": "skor_pl_pga_maluku.csv",
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
                # —— Mode KABUPATEN/KOTA: hanya join satu pulau yang ada
                # di data
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

            # —— Mode NASIONAL: gunakan SATU file nasional (bukan per pulau)
            csv_path = os.path.join(
                data_root, f"skor_pl_{self.JLH.lower()}.csv"
            )  # <— di root jlh_pga
            name = "skor_pl_nasional"
            pl_layer = load_csv_table(csv_path, name)

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
                    "PREFIX": "",  # pastikan nama kolom tetap S_PL
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            # Jaga-jaga: kalau QGIS tetap memberi nama selain S_PL
            # (mis. S_PL_2), samakan ke S_PL
            if not has_field(current, "S_PL"):
                # cari kandidat yang mirip S_PL
                candidates = [
                    f.name()
                    for f in current.fields()
                    if f.name().lower().startswith("s_pl")
                ]
                if candidates:
                    current = processing.run(
                        "qgis:renametablefield",
                        {
                            "INPUT": current,
                            "FIELD": candidates[0],
                            "NEW_NAME": "S_PL",
                            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                        },
                        context=context,
                        feedback=feedback,
                    )["OUTPUT"]

            return current

        # pakai fungsi
        src_pl = join_skor_pl(src_kva)
        feedback.pushInfo(f"✅ Selesai join skor PL ({skor_jlh})")

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
            out_src_temp = src_idx

            if skor_jlh == "Kabupaten/Kota":
                # Kriteria khususL PL == Tubuh Air Alami, Tubuh Air Buatan,
                # Sungai -> JLH = 5
                out_src_kk_poli = {
                    "INPUT": out_src_temp,
                    "FIELD_NAME": f"JLH_{self.JLH}_KK",
                    "FIELD_TYPE": 0,  # Float
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 2,
                    "NEW_FIELD": True,
                    "FORMULA": f"""
                        CASE
                            WHEN \"PL\" IN (
                                'Tubuh Air Alami',
                                'Tubuh Air Buatan',
                                'Sungai') THEN 5
                            ELSE \"JLH_{self.JLH}\"
                        END""",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                }
                out_src = processing.run(
                    "qgis:fieldcalculator", out_src_kk_poli
                )["OUTPUT"]
            else:
                # Kriteria khusus: PL == 'Tubuh Air' → JLH_PengAir_KK = 5,
                # else = JLH_PengAir (hasil SAW)
                out_src_kk_poli = {
                    "INPUT": out_src_temp,
                    "FIELD_NAME": f"JLH_{self.JLH}_KK",
                    "FIELD_TYPE": 0,  # Float
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 2,
                    "NEW_FIELD": True,
                    "FORMULA": f"""
                        CASE
                            WHEN "PL" = 'Tubuh Air' THEN 5
                            ELSE "JLH_{self.JLH}"
                        END
                    """,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                }
                out_src = processing.run(
                    "qgis:fieldcalculator", out_src_kk_poli
                )["OUTPUT"]

        else:
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
                    "FIELD_NAME": "JLH_PengAir_Proporsional",
                    "FIELD_TYPE": 0,
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 2,
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
                    "VALUES_FIELD_NAME": "JLH_PengAir_Proporsional",
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
            out_src = processing.run(
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

            # Jalankan MCA untuk dapatkan LC dominan per GRID
            grid_pl_mca = processing.run(
                "d3tlh:mcagrid",
                {
                    "GRID": grid,
                    "LAYER2": pl,
                    "LAYER2_FIELD": "PL",
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
            )["OUTPUT"]

            # Join PL_MCA ke JLH by ID GRID
            join_pl_mca_jlh = {
                "INPUT": out_src,
                "FIELD": "ID",
                "INPUT_2": grid_pl_mca,
                "FIELD_2": "ID",
                "JOIN_TYPE": 1,
                "FIELDS_TO_COPY": ["PL"],
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            }
            source_join_pl_mca_jlh = processing.run(
                "qgis:joinattributestable", join_pl_mca_jlh
            )["OUTPUT"]

            # Kriteria khusus: PL == 'Tubuh Air' → JLH_PengAir_KK = 5,
            # else = JLH_PengAir (hasil SAW)
            if skor_jlh == "Kabupaten/Kota":
                out_src_kk_grid = {
                    "INPUT": source_join_pl_mca_jlh,
                    "FIELD_NAME": f"JLH_{self.JLH}_KK",
                    "FIELD_TYPE": 0,  # Float
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 2,
                    "NEW_FIELD": True,
                    "FORMULA": f"""
                    CASE
                        WHEN "PL" IN (
                            'Tubuh Air Alami',
                            'Tubuh Air Buatan',
                            'Sungai') THEN 5
                        ELSE "JLH_{self.JLH}"
                    END
                    """,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                }
            else:
                out_src_kk_grid = {
                    "INPUT": source_join_pl_mca_jlh,
                    "FIELD_NAME": f"JLH_{self.JLH}_KK",
                    "FIELD_TYPE": 0,  # Float
                    "FIELD_LENGTH": 20,
                    "FIELD_PRECISION": 2,
                    "NEW_FIELD": True,
                    "FORMULA": f"""
                    CASE
                        WHEN "PL" = 'Tubuh Air' THEN 5
                        ELSE "JLH_{self.JLH}"
                    END
                    """,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                }

            out_src = processing.run(
                "qgis:fieldcalculator", out_src_kk_grid
            )["OUTPUT"]

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
                    WHEN "JLH_{self.JLH}" >= 1.0 AND "JLH_{self.JLH}" <= 1.8
                        THEN 'Sangat Rendah'
                    WHEN "JLH_{self.JLH}" > 1.8 AND "JLH_{self.JLH}" <= 2.6
                        THEN 'Rendah'
                    WHEN "JLH_{self.JLH}" > 2.6 AND "JLH_{self.JLH}" <= 3.4
                        THEN 'Sedang'
                    WHEN "JLH_{self.JLH}" > 3.4 AND "JLH_{self.JLH}" <= 4.2
                        THEN 'Tinggi'
                    WHEN "JLH_{self.JLH}" > 4.2 AND "JLH_{self.JLH}" <= 5.0
                        THEN 'Sangat Tinggi'
                    ELSE 'Tidak Diketahui'
                END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        out_src = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": out_src,
                "FIELD_NAME": f"Kategori_JLH_{self.JLH}_KK",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 20,
                "NEW_FIELD": True,
                "FORMULA": f"""
                CASE
                    WHEN "JLH_{self.JLH}_KK" >= 1.0
                        AND "JLH_{self.JLH}_KK" <= 1.8 THEN 'Sangat Rendah'
                    WHEN "JLH_{self.JLH}_KK" > 1.8
                        AND "JLH_{self.JLH}_KK" <= 2.6 THEN 'Rendah'
                    WHEN "JLH_{self.JLH}_KK" > 2.6
                        AND "JLH_{self.JLH}_KK" <= 3.4 THEN 'Sedang'
                    WHEN "JLH_{self.JLH}_KK" > 3.4
                        AND "JLH_{self.JLH}_KK" <= 4.2 THEN 'Tinggi'
                    WHEN "JLH_{self.JLH}_KK" > 4.2
                        AND "JLH_{self.JLH}_KK" <= 5.0 THEN 'Sangat Tinggi'
                    ELSE 'Tidak Diketahui'
                END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback.pushInfo(
                "✅ Pembuatan kolom kategori JLH Kehati "
                "Kriteria Khusus berhasil"
            ),
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
        return "jlh_pengaturan_air"

    def displayName(self):
        return self.tr("JLH Pengaturan Air")

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

    def shortHelpString(self):
        return self.tr("""
            <b>Indeks Jasa Lingkungan Pengendalian Genangan Air
            (IJLH_PGA)</b><br>
            <i>Flood Regulation Ecosystem Service Index
            (IJLH_PGA)</i>

            <h3>🇮🇩 Deskripsi (Bahasa Indonesia)</h3>

            Algoritma ini digunakan untuk menghitung nilai
            <b>Indeks Jasa Lingkungan Pengendalian Genangan Air
            (IJLH_PGA)</b> yang menggambarkan kemampuan
            ekosistem dalam mengatur aliran air permukaan,
            mengurangi limpasan, serta mencegah genangan atau
            banjir. Metode pengembangan algoritma ini disusun
            berdasarkan <b>Dokumen Petunjuk Teknis D3TLH
            2024</b> dan telah disesuaikan untuk analisis
            spasial di Indonesia.

            <h4>🎯 Tujuan:</h4>

            Menilai kemampuan ekosistem dalam mengendalikan
            genangan air melalui analisis spasial terhadap
            penutup lahan dan karakteristik ekoregion yang
            mempengaruhi daya serap dan pengaturan air.

            <h4>🗺️ Input yang Dibutuhkan:</h4>

            <ul>
                <li><b>1. Peta Tutupan Lahan</b>
                (data vektor dengan kolom
                <code>PL</code>)</li>

                <li><b>2. Peta Ekoregion</b>
                (data vektor dengan kolom
                <code>KBA_250</code> dan
                <code>KVA_250</code>)</li>

                <li><b>3. Data Vektor Grid Area Kajian</b>
                (opsional, digunakan jika bentuk output
                grid)</li>
            </ul>

            <h4>📤 Output:</h4>

            <ul>
                <li>Peta vektor hasil
                <b>Indeks IJLH Pengendalian Genangan Air
                (IJLH_PGA)</b></li>
            </ul>

            <h4>⚙️ Metodologi:</h4>

            Nilai indeks dihitung menggunakan pendekatan
            <b>skoring dan pembobotan</b> berdasarkan
            kombinasi antara jenis penutup lahan dan zona
            ekoregion. Hasil kombinasi menunjukkan tingkat
            kemampuan ekosistem dalam:

            <ul>
                <li>Menahan limpasan permukaan,</li>
                <li>Mengatur aliran air,</li>
                <li>Mengurangi potensi genangan dan
                banjir.</li>
            </ul>

            <h4>🧭 Contoh Penggunaan:</h4>

            1. Pilih area kajian (nasional atau per pulau).
            Jika area kajian berskala pulau, pastikan
            data penutup lahan memiliki kolom
            <code>PULAU</code>.

            2. Pilih bentuk output (Poligon atau Grid).
            Jika menggunakan Grid, wajib menginput
            data Grid dari modul Utility.

            3. Tentukan tahun data penutup lahan.

            4. Input data Penutup Lahan
            (<code>PL</code>) dan Ekoregion
            (<code>KBA_250</code>,
            <code>KVA_250</code>).

            5. (Opsional) Input data Grid untuk analisis
            berbasis grid.

            <h4>📚 Referensi:</h4>

            - Dokumen Petunjuk Teknis D3TLH 2024
            - Dokumen Petunjuk Teknis D3TLH 2025

            <hr>

            <h3>🌍 Description (English)</h3>

            This algorithm calculates the
            <b>Flood Regulation Ecosystem Service Index
            (IJLH_PGA)</b>, representing the ecosystem's
            ability to regulate surface water flow,
            reduce runoff, and prevent flooding or
            waterlogging. The method follows the
            <b>D3TLH Technical Guideline 2024</b> and has
            been adjusted for spatial analysis in
            Indonesia.

            <h4>🎯 Purpose:</h4>

            To assess the ecosystem's capacity to control
            flood and surface water accumulation through
            spatial analysis of land cover and ecoregion
            characteristics.

            <h4>🗺️ Required Inputs:</h4>

            <ul>
                <li><b>Land Cover Map</b>
                (vector data with
                <code>PL</code> field)</li>

                <li><b>Ecoregion Map</b>
                (vector data with
                <code>KBA_250</code> and
                <code>KVA_250</code> fields)</li>

                <li><b>Grid Area Layer</b>
                (optional, required if output type
                is Grid)</li>
            </ul>

            <h4>📤 Output:</h4>

            <ul>
                <li>Vector map of
                <b>Flood Regulation Ecosystem Service
                Index (IJLH_PGA)</b></li>
            </ul>

            <h4>⚙️ Methodology:</h4>

            The index is calculated using a
            <b>scoring and weighting approach</b>
            between land cover and ecoregion
            parameters. The combined classification
            reflects the ecosystem's capacity to:

            <ul>
                <li>Reduce surface runoff,</li>
                <li>Regulate water flow,</li>
                <li>Lower the potential for flooding
                and waterlogging.</li>
            </ul>

            <h4>🧭 Example Workflow:</h4>

            1. Select the study area (national or
            island scale). If island scale,
            ensure land cover data contains a
            <code>PULAU</code> column.

            2. Choose output type (Polygon or Grid).
            If using Grid, provide the Grid layer
            generated via the Utility module.

            3. Specify the land cover data year.

            4. Input the Land Cover
            (<code>PL</code>) and Ecoregion
            (<code>KBA_250</code>,
            <code>KVA_250</code>) datasets.

            5. Optionally input Grid data for
            grid-based analysis.

            <h4>📚 References:</h4>

            - D3TLH Technical Guideline 2024
            - D3TLH Technical Guideline 2025

            <hr>

            <b><i>Notes: Disarankan untuk tidak
            menyimpan output secara temporary.</i></b>
        """)

    def createInstance(self):
        return JLHWaterRegulationAlgorithm()
