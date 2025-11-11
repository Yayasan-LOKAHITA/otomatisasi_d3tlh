# core/field_mappings.py


def build_field_mappings(
    jlh: str, tahun: str, bentuk_output: str, layer=None, area=None
):
    """
    Build field mappings dynamically for each JLH and output type.

    Parameters
    ----------
    jlh : str
        Jenis JLH (e.g. 'PHK', 'PKU', 'PGA', etc.)
    tahun : str
        Tahun string, e.g. '2024'
    bentuk_output : str
        Either 'Poligon' or 'Grid'
    layer : QgsVectorLayer, optional
        Source layer, used to remove missing WADMKC/WADMKD if not exist

    Returns
    -------
    list[dict]
        Final field mappings
    """

    tahun_suffix = str(tahun)[-2:]

    # Common reusable field chunks
    base_admin_fields = [
        {"name": "PULAU", "type": 10, "length": 255, "expression": "PULAU"},
        {"name": "WADMPR", "type": 10, "length": 255, "expression": "WADMPR"},
        {"name": "WADMKK", "type": 10, "length": 255, "expression": "WADMKK"},
        {"name": "WADMKC", "type": 10, "length": 255, "expression": "WADMKC"},
        {"name": "WADMKD", "type": 10, "length": 255, "expression": "WADMKD"},
    ]

    grid_prefix = [{"name": "ID", "type": 10, "expression": "ID"}]

    kba_kva_fields = [
        {"name": "KBA_250", "type": 10, "expression": "KBA_250"},
        {"name": "KVA_250", "type": 10, "expression": "KVA_250"},
        {"name": f"PL{tahun_suffix}", "type": 10, "expression": "PL"},
        {"name": f"KBA_{jlh}", "type": 6, "expression": "S_EK"},
        {"name": f"KVA_{jlh}", "type": 6, "expression": "S_VE"},
        {"name": f"PL{tahun_suffix}_{jlh}", "type": 6, "expression": "S_PL"},
    ]

    def round_expr(expr):
        return f'round("{expr}",2)'

    # Base measurement fields
    common_value_fields = [
        {
            "name": f"{jlh}_{tahun_suffix}",
            "type": 6,
            "precision": 2,
            "expression": round_expr(f"JLH_{jlh}"),
        },
        {
            "name": f"K{jlh}_{tahun_suffix}",
            "type": 10,
            "expression": f"Kategori_JLH_{jlh}",
        },
    ]

    common_value_fields_kk = [
        {
            "name": f"{jlh}_{tahun_suffix}_KK",
            "type": 6,
            "precision": 2,
            "expression": round_expr(f"JLH_{jlh}_KK"),
        },
        {
            "name": f"K{jlh}_{tahun_suffix}_KK",
            "type": 10,
            "expression": f"Kategori_JLH_{jlh}_KK",
        },
    ]

    # Default output
    mappings = []

    # ---- CASE SELECTION ----
    if jlh == "PHK":
        if bentuk_output == "Poligon":
            mappings = (
                base_admin_fields
                + kba_kva_fields
                + common_value_fields
                + common_value_fields_kk
            )
        else:  # Grid
            mappings = (
                grid_prefix
                + base_admin_fields
                + common_value_fields
                + common_value_fields_kk
            )

    elif jlh == "PKU":
        if bentuk_output == "Poligon":
            mappings = base_admin_fields + kba_kva_fields + common_value_fields
        else:
            mappings = grid_prefix + base_admin_fields + common_value_fields

    elif jlh == "PGA":
        if bentuk_output == "Poligon":
            mappings = (
                base_admin_fields
                + kba_kva_fields
                + common_value_fields
                + common_value_fields_kk
            )
        else:
            mappings = (
                grid_prefix
                + base_admin_fields
                + common_value_fields
                + common_value_fields_kk
            )

    elif jlh == "PYA":
        if area == "Kabupaten/Kota":
            if bentuk_output == "Poligon":
                mappings = (
                    base_admin_fields
                    + kba_kva_fields
                    + common_value_fields
                    + common_value_fields_kk
                )
            else:
                mappings = (
                    grid_prefix
                    + base_admin_fields
                    + common_value_fields
                    + common_value_fields_kk
                )
        else:
            if bentuk_output == "Poligon":
                mappings = base_admin_fields + kba_kva_fields + common_value_fields
            else:
                mappings = grid_prefix + base_admin_fields + common_value_fields

    elif jlh == "PGN":
        if bentuk_output == "Poligon":
            mappings = base_admin_fields + kba_kva_fields + common_value_fields
        else:
            mappings = grid_prefix + base_admin_fields + common_value_fields

    elif jlh == "PPK":
        if bentuk_output == "Poligon":
            mappings = base_admin_fields + kba_kva_fields + common_value_fields
        else:
            mappings = grid_prefix + base_admin_fields + common_value_fields

    # Remove WADMKC/WADMKD if not present in layer
    if layer is not None:
        existing = [f.name() for f in layer.fields()]
        mappings = [
            m
            for m in mappings
            if not (m["name"] in ["WADMKC", "WADMKD"] and m["name"] not in existing)
        ]

    return mappings
