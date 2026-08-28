# core/field_mappings.py


def build_field_mappings_jlh(
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
            mappings = (
                base_admin_fields + kba_kva_fields + common_value_fields
            )
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

    elif jlh == "PGN":
        if bentuk_output == "Poligon":
            mappings = (
                base_admin_fields + kba_kva_fields + common_value_fields
            )
        else:
            mappings = grid_prefix + base_admin_fields + common_value_fields

    elif jlh == "PPK":
        if bentuk_output == "Poligon":
            mappings = (
                base_admin_fields + kba_kva_fields + common_value_fields
            )
        else:
            mappings = grid_prefix + base_admin_fields + common_value_fields

    # Remove WADMKC/WADMKD if not present in layer
    if layer is not None:
        existing = [f.name() for f in layer.fields()]
        mappings = [
            m
            for m in mappings
            if not (
                m["name"] in ["WADMKC", "WADMKD"]
                and m["name"] not in existing
            )
        ]

    return mappings


def build_field_mappings_ikp(
    ikp_type: str, bentuk_output: str, tahun: str, layer=None
):
    """
    Return field mappings for IKP (Kehati, Udara, or Lahan).

    Parameters
    ----------
    ikp_type : str
        One of ["kehati", "udara", "lahan"].
    bentuk_output : str
        One of ["grid", "poligon"].
    tahun : str
        Year string, e.g. "2025" (used for YY suffix).

    Returns
    -------
    list of dict
        Each dict is { "name": ..., "type": ..., "expression": ... }.
    """

    YY = tahun[-2:]
    base_fields = [
        {"name": "ID", "type": 10, "expression": "ID"},
        {"name": "WADMPR", "type": 10, "expression": "WADMPR"},
        {"name": "WADMKK", "type": 10, "expression": "WADMKK"},
        {"name": "WADMKC", "type": 10, "expression": "WADMKC"},
        {"name": "WADMKD", "type": 10, "expression": "WADMKD"},
    ]

    # --- Remove WADMKC / WADMKD if not in layer fields ---
    if layer is not None:
        existing_fields = [f.name() for f in layer.fields()]
        base_fields = [
            f
            for f in base_fields
            if f["name"] not in ["WADMKC", "WADMKD"]
            or f["name"] in existing_fields
        ]

    if ikp_type.lower() == "kehati":
        if bentuk_output.lower() == "grid":
            extra_fields = [
                {"name": "IKPKHT", "type": 6, "expression": "IKPKHT"},
                {"name": "SIKPKHT", "type": 2, "expression": "SIKPKHT"},
                {"name": "KIKPKHT", "type": 10, "expression": "KIKPKHT"},
            ]
        elif bentuk_output.lower() == "poligon":
            extra_fields = [
                {"name": f"PPK_{YY}", "type": 6, "expression": f"PPK_{YY}"},
                {"name": f"PGN_{YY}", "type": 6, "expression": f"PGN_{YY}"},
                {
                    "name": f"PGA_{YY}_KK",
                    "type": 6,
                    "expression": f"PGA_{YY}_KK",
                },
                {
                    "name": f"PHK_{YY}_KK",
                    "type": 6,
                    "expression": f"PHK_{YY}_KK",
                },
                {"name": "BCPI", "type": 6, "expression": "BCPI"},
                {"name": "KLS_BCPI", "type": 10, "expression": "KLS_BCPI"},
                {"name": "KLS_KG", "type": 6, "expression": "KLS_KG"},
                {"name": "KLS_RTE", "type": 6, "expression": "KLS_RTE"},
                {"name": "KLS_HAB_KK", "type": 6, "expression": "KLS_HAB_KK"},
                {"name": "KLS_KONEK", "type": 6, "expression": "KLS_KONEK"},
                {"name": "BI", "type": 6, "expression": "BI"},
                {"name": "KLS_BI", "type": 6, "expression": "KLS_BI"},
                {"name": "IKPKHT", "type": 6, "expression": "IKPKHT"},
                {"name": "SIKPKHT", "type": 2, "expression": "SIKPKHT"},
                {"name": "KIKPKHT", "type": 10, "expression": "KIKPKHT"},
            ]
        else:
            raise ValueError(
                "bentuk_output must be 'grid' or 'poligon' for Kehati"
            )

    elif ikp_type.lower() == "udara":
        if bentuk_output.lower() == "grid":
            extra_fields = [
                {"name": "IKPUDR", "type": 6, "expression": "IKPUDR"},
                {"name": "SIKPUDR", "type": 2, "expression": "SIKPUDR"},
                {"name": "KIKPUDR", "type": 10, "expression": "KIKPUDR"},
            ]
        elif bentuk_output.lower() == "poligon":
            extra_fields = [
                {"name": f"PKU_{YY}", "type": 6, "expression": f"PKU_{YY}"},
                {
                    "name": f"KPKU_{YY}",
                    "type": 10,
                    "expression": f"KPKU_{YY}",
                },
                {"name": "SPKU", "type": 2, "expression": "SPKU"},
                {"name": "PM25", "type": 6, "expression": "PM25"},
                {"name": "SPM25", "type": 2, "expression": "SPM25"},
                {"name": "SKOR", "type": 10, "expression": "SKOR"},
                {"name": "IPS", "type": 2, "expression": "IPS"},
                {"name": "SIPS", "type": 2, "expression": "SIPS"},
                {"name": "IKPUDR", "type": 6, "expression": "IKPUDR"},
                {"name": "SIKPUDR", "type": 2, "expression": "SIKPUDR"},
                {"name": "KIKPUDR", "type": 10, "expression": "KIKPUDR"},
            ]
        else:
            raise ValueError(
                "bentuk_output must be 'grid' or 'poligon' for Udara"
            )

    elif ikp_type.lower() == "lahan":
        if bentuk_output.lower() != "grid":
            raise ValueError("IKP Lahan only supports 'grid' data type")
        extra_fields = [
            {"name": "KET_HA", "type": 6, "expression": "KET_HA"},
            {"name": f"POPGRID{YY}", "type": 2, "expression": f"POPGRID{YY}"},
            {"name": "SJEPGN", "type": 6, "expression": "SJEPGN"},
            {"name": "SJEBUILT", "type": 6, "expression": "SJEBUILT"},
            {"name": "SJELHN", "type": 6, "expression": "SJELHN"},
            {"name": "AB_POP", "type": 2, "expression": "AB_POP"},
            {"name": "D_POP", "type": 2, "expression": "D_POP"},
            {"name": "STATUSPGN", "type": 10, "expression": "STATUSPGN"},
            {"name": "IKPLHN", "type": 6, "expression": "IKPLHN"},
            {"name": "SIKPLHN", "type": 2, "expression": "SIKPLHN"},
            {"name": "KIKPLHN", "type": 10, "expression": "KIKPLHN"},
        ]
    else:
        raise ValueError(
            "ikp_type must be one of 'kehati', 'udara', or 'lahan'"
        )

    return base_fields + extra_fields
