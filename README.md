# otomatisasi_d3tlh

Plugin QGIS untuk otomatisasi analisis **Daya Dukung dan Daya Tampung Lingkungan Hidup (D3TLH)** berbasis grid, mencakup perhitungan **JLH (Jasa Lingkungan Hidup)**, **IKP (Indeks Kemampuan Pemanfaatan)**, serta integrasi indikator lingkungan untuk analisis spasial perencanaan.

A QGIS plugin for automating **Environmental Carrying Capacity and Environmental Capacity (D3TLH)** analysis using a grid-based approach, including **Ecosystem Services Index (JLH)**, **Utilization Capability Index (IKP)**, and integrated environmental indicators for spatial planning.

<p>
  <strong>QGIS:</strong> ≥ 3.40 (LTR OK) •
  <strong>OS:</strong> Windows / Linux / macOS •
  <strong>License:</strong> GPL-3.0+
</p>

## Features
- **A. Utilities:** Atribut Dominan per Grid (Maximum Combined Area), SGSRI (Sistem Grid Skala Ragam Indonesia).
- **B. Preprocessing:** Klasifikasi Penutupan Lahan & Kawasan Hutan (KLHK), Penambahan atribut pulau, Pengecekan kualitas data, Standardisasi kelas jalan, Standardisasi skema data.
- **C. Indeks Jasa Lingkungan Hidup (JLH):** JLH Pendukung Habitat & Keanekaragaman Hayati, JLH Pengatur Kualitas Udara, JLH Pengaturan Air, JLH Penyedia Air, JLH Penyedia Pangan, JLH Penyerapan & Penyimpanan Karbon.
- **D. Demographic & Ecological Model:** Model distribusi penduduk (grid-based), Model jejak ekologis.
- **E. Indeks Kemampuan Pemanfaatan (IKP):** IKP Air, IKP Kehati, IKP Lahan, IKP Udara.
- **F. Integration:** Integrasi IKP Lingkungan Hidup (komposit multi-indikator).
- **G. Styling:** Otomatisasi simbologi peta.

## Installation
**A) From release ZIP (recommended)**
1. Download the latest `.zip` from **Releases**.  
2. QGIS → *Plugins* → *Manage and Install…* → *Install from ZIP* → choose the file.

**B) From source**
```bash
git clone https://github.com/Yayasan-LOKAHITA/Otomatisasi-D3TLH.git
# Copy the 'AMERTA' folder into your QGIS plugins directory:
# Windows: %AppData%\QGIS\QGIS3\profiles\default\python\plugins\
# Linux:   ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
# macOS:   ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/
# Restart QGIS, then enable the plugin (Plugins → Manage and Install…)
```

## Quickstart
1. Enable the plugin (Plugins → Manage and Install… → search “**Otomatisasi D3TLH**”). 
2. Open Processing Toolbox → **Otomatisasi D3TLH** group.

## Typical flow
Inputs:
- Data penutupan lahan (PL) - Land cover data
- Data biofisik (tanah, topografi, dll) - Biophysical data (soil, terrain, etc.)
- Data hidrologi - Hydrological data
- Data kependudukan - Population data
- Batas wilayah (AOI) - Area of Interest (AOI)

Process:
1. Preprocessing
   Data cleaning and standardization
2. Grid Generation (SGSRI)
   Multi-scale spatial grid
3. Indicator Calculation
   - JLH (ecosystem services)
   - IKP (utilization capability)
4. Integration
   Composite environmental index
5. Output Generation
   Grid-based spatial layer

Outputs:
Grid layer with attributes:
- JLH indicators
- IKP indicators
- Composite IKP

## Reporting Issues / Contributing
- Open an Issue with QGIS version, OS, steps to reproduce, and logs/screenshots.
- PRs welcome—keep folder structure consistent and, when possible, include tiny test data.

## Citation
If you use Otomatisasi D3TLH in publications, please cite (APA 7th):
<p>Kurniawan, F. A. D., Safitri, S., Norvyani, D. A., Rahmadani, S., & Wibowo, F. R. (2025).
Otomatisasi D3TLH: QGIS Plugin for Environmental Carrying Capacity and Environmental Capacity Analysis (v1.1.0) [Computer software]. The Ministry of Environment of the Republic of Indonesia. https://github.com/Yayasan-LOKAHITA/Otomatisasi-D3TLH</p>

## License & Credits
Released under GNU GPL-3.0 or later. See LICENSE.
<p><strong>Authors</strong>: Fadillah Azhar Deaudin Kurniawan, Sitarani Safitri, Dini Aprilia Norvyani, Suchi Rahmadani, Fariz Rizaldy Wibowo (see metadata.txt).</p>

<p><strong>Acknowledgments</strong>: This plugin is developed with reference to standards, datasets, and frameworks provided by the Ministry of Environment of the Republic of Indonesia, particularly in the context of Environmental Carrying Capacity and Environmental Capacity (D3TLH) analysis.
We also acknowledge Yayasan Lokahita for their support in the development and implementation of this plugin.
