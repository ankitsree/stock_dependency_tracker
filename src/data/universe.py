"""Satellite candidate pool for Phase 1.

The roadmap's long-term plan is to derive this from a downloaded index
constituent list (Russell 2000 / S&P 600) filtered by market cap and volume.
For the Phase 1 proof of concept we skip the screener step and use a
curated, hand-picked list of small/mid-cap semiconductor, hardware, and
datacenter-adjacent tickers plausible as NVDA satellites.
"""

import pandas as pd

SATELLITE_UNIVERSE = [
    ("AEIS", "Advanced Energy Industries", "Semiconductor Equipment"),
    ("ACLS", "Axcelis Technologies", "Semiconductor Equipment"),
    ("ALGM", "Allegro MicroSystems", "Semiconductors"),
    ("AMBA", "Ambarella", "Semiconductors"),
    ("AOSL", "Alpha and Omega Semiconductor", "Semiconductors"),
    ("AXTI", "AXT Inc", "Semiconductor Materials"),
    ("CAMT", "Camtek", "Semiconductor Equipment"),
    ("CEVA", "CEVA Inc", "Semiconductor IP"),
    ("COHU", "Cohu Inc", "Semiconductor Equipment"),
    ("CRUS", "Cirrus Logic", "Semiconductors"),
    ("DIOD", "Diodes Incorporated", "Semiconductors"),
    ("FORM", "FormFactor", "Semiconductor Equipment"),
    ("ICHR", "Ichor Holdings", "Semiconductor Equipment"),
    ("IPGP", "IPG Photonics", "Laser/Photonics"),
    ("KLIC", "Kulicke & Soffa", "Semiconductor Equipment"),
    ("LSCC", "Lattice Semiconductor", "Semiconductors"),
    ("MKSI", "MKS Instruments", "Semiconductor Equipment"),
    ("MTSI", "MACOM Technology", "Semiconductors"),
    ("MXL", "MaxLinear", "Semiconductors"),
    ("NVMI", "Nova Ltd", "Semiconductor Equipment"),
    ("ONTO", "Onto Innovation", "Semiconductor Equipment"),
    ("PDFS", "PDF Solutions", "EDA Software"),
    ("PLAB", "Photronics", "Semiconductor Materials"),
    ("POWI", "Power Integrations", "Semiconductors"),
    ("QRVO", "Qorvo", "Semiconductors"),
    ("RMBS", "Rambus", "Semiconductor IP"),
    ("SITM", "SiTime", "Semiconductors"),
    ("SLAB", "Silicon Labs", "Semiconductors"),
    ("SMTC", "Semtech", "Semiconductors"),
    ("SYNA", "Synaptics", "Semiconductors"),
    ("UCTT", "Ultra Clean Holdings", "Semiconductor Equipment"),
    ("VECO", "Veeco Instruments", "Semiconductor Equipment"),
    ("WOLF", "Wolfspeed", "Semiconductor Materials"),
    ("SGH", "SMART Global Holdings", "Memory/Hardware"),
    ("ACMR", "ACM Research", "Semiconductor Equipment"),
    ("CRDO", "Credo Technology", "Semiconductors"),
    ("NVTS", "Navitas Semiconductor", "Semiconductors"),
    ("INDI", "Indie Semiconductor", "Semiconductors"),
    ("MRAM", "Everspin Technologies", "Memory"),
    ("PI", "Impinj", "Semiconductors"),
    ("FN", "Fabrinet", "Contract Manufacturing"),
    ("AEHR", "Aehr Test Systems", "Semiconductor Equipment"),
    ("ATOM", "Atomera", "Semiconductor IP"),
    ("OSIS", "OSI Systems", "Electronic Systems"),
    ("NTGR", "Netgear", "Networking Hardware"),
    ("INFN", "Infinera", "Optical Networking"),
    ("VIAV", "Viavi Solutions", "Test & Measurement"),
    ("CALX", "Calix", "Networking Hardware"),
    ("EXTR", "Extreme Networks", "Networking Hardware"),
    ("SANM", "Sanmina", "Contract Manufacturing"),
    ("PLXS", "Plexus Corp", "Contract Manufacturing"),
    ("BHE", "Benchmark Electronics", "Contract Manufacturing"),
    ("CTS", "CTS Corp", "Electronic Components"),
    ("ROG", "Rogers Corporation", "Electronic Materials"),
    ("NN", "NN Inc", "Precision Components"),
]


def load_universe() -> pd.DataFrame:
    """Return the Phase 1 satellite candidate pool as a metadata DataFrame."""
    return pd.DataFrame(SATELLITE_UNIVERSE, columns=["ticker", "name", "sector"])
