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

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsFeatureSink,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFile,
    QgsProcessingParameterBoolean,
    QgsProcessingException,
    QgsCoordinateReferenceSystem,
    QgsWkbTypes,
)
import os
from typing import Dict, Tuple, Optional
import zipfile
import re
from ... import dependencies
from defusedxml import ElementTree as ET
from qgis.PyQt.QtGui import QIcon


def _colrow(cell_ref: str):
    m = re.match(r"^([A-Z]+)(\d+)$", cell_ref)
    return (m.group(1), int(m.group(2))) if m else (None, None)


def _read_shared_strings(z: zipfile.ZipFile):
    try:
        with z.open("xl/sharedStrings.xml") as f:
            root = ET.parse(f).getroot()
    except KeyError:
        return []
    ns = {
        "t": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    }
    res = []
    for si in root.findall("t:si", ns):
        ts = [t.text or "" for t in si.findall(".//t:t", ns)]
        if not ts:
            tnode = si.find("t:t", ns)
            ts = [(tnode.text or "") if tnode is not None else ""]
        res.append("".join(ts))
    return res


def _first_sheet_path(z: zipfile.ZipFile) -> str:
    with z.open("xl/workbook.xml") as f:
        wb = ET.parse(f).getroot()
    ns = {
        "t": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org"
        "/officeDocument/2006/relationships",
    }
    sheet = wb.find(".//t:sheets/t:sheet", ns)
    if sheet is None:
        raise QgsProcessingException("Workbook tidak berisi sheet.")
    rId = sheet.attrib.get(
        "{http://schemas.openxmlformats.org/officeDocument"
        "/2006/relationships}id"
    )
    with z.open("xl/_rels/workbook.xml.rels") as f:
        rels = ET.parse(f).getroot()
    nsr = {
        "t": "http://schemas.openxmlformats.org/package/2006/relationships"
    }
    target = None
    for rel in rels.findall("t:Relationship", nsr):
        if rel.attrib.get("Id") == rId:
            target = rel.attrib.get("Target")
            break
    if not target:
        raise QgsProcessingException(
            "Gagal menemukan path sheet pertama."
        )
    return "xl/" + target


def _read_sheet_cells(
    xlsx_path: str, wanted_cols=("B", "C", "D", "E"), max_row=2000
):
    try:
        with zipfile.ZipFile(xlsx_path) as z:
            shared = _read_shared_strings(z)
            with z.open(_first_sheet_path(z)) as f:
                root = ET.parse(f).getroot()
    except zipfile.BadZipFile:
        raise QgsProcessingException("File bukan .xlsx valid.")
    ns = {
        "t": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    }
    rows = {}
    for rnode in root.findall(".//t:sheetData/t:row", ns):
        r = int(rnode.attrib.get("r", "0") or "0")
        if r > max_row:
            continue
        for c in rnode.findall("t:c", ns):
            ref = c.attrib.get("r", "")
            col, _row = _colrow(ref)
            if col not in wanted_cols:
                continue
            t = c.attrib.get("t")
            v = c.find("t:v", ns)
            is_node = c.find("t:is", ns)
            if t == "s" and v is not None:
                idx = int(v.text)
                val = shared[idx] if 0 <= idx < len(shared) else ""
                typ = "s"
            elif t == "inlineStr" and is_node is not None:
                txt = "".join(
                    [
                        (tn.text or "")
                        for tn in is_node.findall(".//t:t", ns)
                    ]
                )
                val = txt
                typ = "str"
            else:
                val = v.text if v is not None else None
                typ = "n"
            rows.setdefault(r, {})[col] = (typ, val)
    return rows


def _num(cell):
    if cell is None:
        return None
    typ, txt = cell
    if txt is None:
        return None
    try:
        return float(txt)
    except (ValueError, TypeError):
        try:
            return float(str(txt).replace(",", ""))
        except (ValueError, TypeError):
            return None


def _txt(cell):
    if cell is None:
        return None
    return cell[1] if cell[1] is not None else None


# ----------------------- Algoritma QGIS (tabel-only) -----------------------
class SocioEcoEcologicalFootprintAlgorithm(QgsProcessingAlgorithm):
    """
    Model Jejak Ekologis — output tabel (no-geometry).
    LPij pangan: pakai produktivitas; jika 0/tidak ada → FIj polinom berbasis
    tahun (C2). Kolom hasil: TAHUN, POPULASI, PANGAN, SANDANG, PAPAN,
    BUILTUP, EF_CAP_YEAR, TOTAL_HA
    """

    OUTPUT = "OUTPUT"
    EXCEL = "EXCEL"
    VERBOSE = "VERBOSE"

    # Konstanta pangan (urut 0..8)
    # 0 Padi, 1 Umbi, 2 Hewani, 3 Minyak&Lemak, 4 Biji Berminyak,
    # 5 Kacang, 6 Gula, 7 Sayur&Buah, 8 Bumbu&Minuman
    _Kbj = [
        383250,
        45990,
        91980,
        76650,
        22995,
        38325,
        38325,
        45990,
        22995,
    ]
    _Ej = [
        363.32,
        120.0,
        160.509,
        1000.0,
        572.72,
        283.78,
        338.709,
        48.09,
        63.0,
    ]
    _IPj = [1.0] * 9

    # Pemetaan label (mutually-exclusive)
    _KW_ORDERED = [
        (0, ["padi-padian", "padi padian", "total padi", "padi"]),
        (1, ["umbi-umbian", "umbi umbian", "total umbi", "umbi"]),
        (
            2,
            [
                "pangan hewani",
                "hewani",
                "ternak",
                "daging",
                "telur",
                "susu",
            ],
        ),
        (3, ["minyak dan lemak", "minyak & lemak"]),
        (
            4,
            [
                "buah / biji berminyak",
                "biji berminyak",
                "buah berminyak",
            ],
        ),
        (5, ["kacang-kacangan", "kacang kacangan", "total kacang"]),
        (6, ["total gula", "gula"]),
        (7, ["sayur dan buah", "sayur & buah", "sayuran dan buah"]),
        (8, ["aneka bumbu", "bumbu", "bahan minuman"]),
    ]

    # ---------- FIj polinomial (ha/kg) bila produktivitas 0 ----------
    @staticmethod
    def _fij_regression(idx: int, year: int) -> float:
        t = float(year - 2016)
        if idx == 0:
            val = (
                3.309562804
                + 0.00279158725 * t
                - 0.000909623865 * t * t
                + 0.0000219147019 * t * t * t
            ) / 1000.0
        elif idx == 1:
            val = (
                0.6757
                - 0.00442074028 * t
                + 0.0000856109743 * t * t
                - 0.00000393199234 * t * t * t
            ) / 10000.0
        elif idx == 2:
            val = (
                0.000496084258064184
                + 0.000000671177176 * t
                - 0.0000000675256016 * t * t
                + 0.00000000181314847 * t * t * t
            ) / 10000.0
        elif idx == 3:
            val = (
                3.05964636457972
                - 0.177706769994872 * t
                + 0.00496665316792903 * t * t
                - 0.000054827359137616 * t * t * t
            ) / 10000.0
        elif idx == 4:
            val = (
                10.4795490929006
                - 0.148623145 * t
                + 0.000728202258 * t * t
                + 0.0000911033598 * t * t * t
            ) / 10000.0
        elif idx == 5:
            val = (
                6.92637146880103
                - 0.0230684652 * t
                - 0.000327768792 * t * t
                + 0.00000744868383 * t * t * t
            ) / 10000.0
        elif idx == 6:
            val = (
                1.6606983384315
                - 0.0134741306328057 * t
                + 0.000174367155979212 * t * t
                - 0.00000267060997992912 * t * t * t
            ) / 10000.0
        elif idx == 7:
            val = (
                0.783582927451816
                - 0.000928187145033807 * t
                + 0.00000262580886186926 * t * t
                - 0.0000000706920282445655 * t * t * t
            ) / 10000.0
        elif idx == 8:
            val = 0.00005
        else:
            val = 0.0
        return max(val, 0.0)

    @staticmethod
    def _papan_fi_ha_per_m3(year: int) -> float:
        return 1.0 / (
            (1.26 + 0.0002666667 * (year - 2015) ** 2) * 10000.0
        )

    @staticmethod
    def _sandang_fij(
        year: int, productivity_kg_per_ha: Optional[float]
    ) -> float:
        if productivity_kg_per_ha and productivity_kg_per_ha > 0:
            return 1.0 / productivity_kg_per_ha
        return (
            37.0574247098412
            - 0.010487380236217 * (year - 2016) / 10000.0
        )

    @staticmethod
    def _norm(s: str) -> str:
        s = s.strip().lower().replace("&", " dan ").replace("/", " / ")
        while "  " in s:
            s = s.replace("  ", " ")
        return s

    def _log(self, msg: str):
        if hasattr(self, "feedback") and self.feedback:
            self.feedback.pushInfo(msg)

    # ---------- baca input dari XLSX ----------
    def _read_inputs_from_excel(
        self, xlsx_path: str, verbose=False
    ) -> Dict[str, float]:
        rows = _read_sheet_cells(
            xlsx_path, wanted_cols=("B", "C", "D", "E"), max_row=2000
        )

        year = _num(rows.get(2, {}).get("C"))
        pop = _num(rows.get(3, {}).get("C"))
        if year is None or pop is None:
            raise QgsProcessingException(
                "Excel tidak memuat TAHUN (C2) dan POPULASI (C3)."
            )
        year = int(year)
        pop = int(pop)

        papan_m3cap = None
        builtup_m2cap = None
        sandang_kb = None
        totals_raw: Dict[str, Tuple[float, float]] = {}

        for r, cols in rows.items():
            btxt = _txt(cols.get("B"))
            if not isinstance(btxt, str):
                continue
            bnorm = self._norm(btxt)
            c = _num(cols.get("C"))  # luas (Ha)
            d = _num(cols.get("D"))  # produksi (ton)
            e = _num(cols.get("E"))  # produksi (kg)

            if "konsumsi kayu per tahun" in bnorm and c is not None:
                papan_m3cap = float(c)
            if bnorm == "total" and c is not None:
                builtup_m2cap = float(c)
            if "kapas" in bnorm:
                if c is not None and c > 0:
                    sandang_kb = float(c)
                elif d is not None and d > 0:
                    sandang_kb = float(d)

            if bnorm.startswith("total "):
                if (c is not None and c > 0) and (
                    (e is not None and e > 0)
                    or (d is not None and d > 0)
                ):
                    prodkg = (
                        float(e)
                        if (e is not None and e > 0)
                        else (float(d) * 1000.0)
                    )
                    totals_raw[btxt] = (float(c), prodkg)

        if papan_m3cap is None:
            raise QgsProcessingException(
                "Tidak menemukan 'Konsumsi Kayu per tahun' (m³/kap/tahun)."
            )
        if builtup_m2cap is None:
            raise QgsProcessingException(
                "Tidak menemukan 'Built-up Land — Total (m²/kap)'."
            )
        if sandang_kb is None:
            sandang_kb = 1.7

        if verbose:
            self._log(
                f"[DEBUG] YEAR={year} POP={pop} PAPAN_m3={papan_m3cap} "
                f"BUILTUP_m2={builtup_m2cap} Kb={sandang_kb}"
            )
            for k, (lu, pr) in totals_raw.items():
                self._log(
                    f"[DEBUG] totals: '{k}' luas={lu} produksi_kg={pr}"
                )

        return dict(
            year=year,
            population=pop,
            papan_m3cap=papan_m3cap,
            builtup_m2cap=builtup_m2cap,
            sandang_kb=sandang_kb,
            totals_raw=totals_raw,
        )

    def _map_totals(
        self, totals_raw: Dict[str, Tuple[float, float]], verbose=False
    ) -> Dict[int, Tuple[float, float, str]]:
        mapped: Dict[int, Tuple[float, float, str]] = {}
        for label, val in totals_raw.items():
            lab_norm = self._norm(label)
            for idx, kws in self._KW_ORDERED:
                if any(kw in lab_norm for kw in kws):
                    mapped.setdefault(idx, (val[0], val[1], label))
                    break
        if verbose:
            for i, v in mapped.items():
                self._log(
                    f"[DEBUG] match[{i}] <- '{v[2]}'  luas={v[0]} "
                    f"prod_kg={v[1]}"
                )
        return mapped

    def _compute_pangan(
        self,
        mapped: Dict[int, Tuple[float, float, str]],
        year: int,
        verbose=False,
    ) -> float:
        total = 0.0
        for idx in range(9):
            if idx in mapped:
                luas, prodkg, label = mapped[idx]
                prod = (
                    (prodkg / luas)
                    if (luas > 0 and prodkg > 0)
                    else 0.0
                )
                if prod > 0:
                    FIj = 1.0 / prod
                    src = "prod"
                else:
                    FIj = self._fij_regression(idx, year)
                    src = "poly"
            else:
                FIj = self._fij_regression(idx, year)
                src = "poly"
                label = "(tak ditemukan)"

            mass_kg = (self._Kbj[idx] / self._Ej[idx]) * 0.1
            LPij = mass_kg * (FIj / self._IPj[idx])
            total += LPij

            if verbose:
                self._log(
                    f"[DEBUG] idx{idx} '{label}': FIj={FIj:.8f} ({src}) "
                    f"mass_kg={mass_kg:.6f} LPij={LPij:.9f}"
                )

        if verbose:
            self._log(f"[DEBUG] PANGAN total = {total:.12f}")
        return total

    # --------------------- QGIS plumbing ---------------------
    def initAlgorithm(self, config):
        # Tanpa input layer — hanya Excel + opsi debug
        self.addParameter(
            QgsProcessingParameterFile(
                self.EXCEL,
                self.tr(
                    "File Excel input (kebutuhan_lahan_input_1.xlsx)"
                ),
                extension="xlsx",
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.VERBOSE,
                self.tr("Tampilkan log detail (debug)"),
                defaultValue=False,
            )
        )
        # Output: table (no-geometry)
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("Output table")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        self.feedback = feedback
        xlsx_path = self.parameterAsFile(
            parameters, self.EXCEL, context
        )
        verbose = bool(
            self.parameterAsBool(parameters, self.VERBOSE, context)
        )
        if not xlsx_path:
            raise QgsProcessingException(
                "Harap pilih file Excel input."
            )

        inp = self._read_inputs_from_excel(xlsx_path, verbose=verbose)
        year = int(inp["year"])
        pop = int(inp["population"])
        papan_m3 = float(inp["papan_m3cap"])
        builtup_m2 = float(inp["builtup_m2cap"])
        sandang_kb = float(inp["sandang_kb"])

        mapped = self._map_totals(inp["totals_raw"], verbose=verbose)
        pangan = self._compute_pangan(
            mapped, year=year, verbose=verbose
        )

        fij_sandang = self._sandang_fij(
            year, productivity_kg_per_ha=None
        )
        sandang = sandang_kb * fij_sandang
        papan = self._papan_fi_ha_per_m3(year) * papan_m3
        builtup = builtup_m2 / 10000.0
        ef_cap_year = pangan + sandang + papan + builtup
        total_ha = ef_cap_year * pop

        # ---- siapkan table schema (no geometry) ----
        out_fields = QgsFields()
        for f in [
            QgsField("TAHUN", QVariant.Int),
            QgsField("POPULASI", QVariant.LongLong),
            QgsField("PANGAN", QVariant.Double),
            QgsField("SANDANG", QVariant.Double),
            QgsField("PAPAN", QVariant.Double),
            QgsField("BUILTUP", QVariant.Double),
            QgsField("EF_CAP_YEAR", QVariant.Double),
            QgsField("TOTAL_HA", QVariant.Double),
        ]:
            out_fields.append(f)

        crs = QgsCoordinateReferenceSystem(
            "EPSG:4326"
        )  # placeholder aman untuk tabel
        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            QgsWkbTypes.NoGeometry,
            crs,
        )

        # satu baris ringkasan
        feat = QgsFeature(out_fields)
        feat.setAttributes(
            [
                year,
                pop,
                float(pangan),
                float(sandang),
                float(papan),
                float(builtup),
                float(ef_cap_year),
                float(total_ha),
            ]
        )
        sink.addFeature(feat, QgsFeatureSink.FastInsert)

        return {self.OUTPUT: dest_id}

    # ---------- metadata (tetap) ----------
    def name(self):
        return "Model Jejak Ekologis"

    def displayName(self):
        return self.tr(self.name())

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return "D. Demographic and Ecological Model"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(__file__),
                "04 Demographic Modelling.svg",
            )
        )

    def shortHelpString(self):
        return self.tr(
            "This module calculates the Ecological Footprint (Jejak "
            "Ekologis) of a region based on statistical data representing "
            "population consumption and land requirements.\n\n"
            "The ecological footprint measures the amount of biologically "
            "productive land and water area required to support human "
            "activities, including food consumption, clothing needs, "
            "housing requirements, and built-up areas.\n\n"
            "The resulting table can be used as an input for "
            "environmental carrying capacity analysis, sustainable "
            "development assessments, and D3TLH workflows.\n\n"
            "<b>Complete explanation read here: "
            "<a href='https://yayasan-lokahita.github.io/"
            "otomatisasi_d3tlh-docs/socio/eco_footprint/'>here</a>.</b>"
        )

    def createInstance(self):
        return SocioEcoEcologicalFootprintAlgorithm()

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)
