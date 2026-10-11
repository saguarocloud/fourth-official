"""The fictional Meridian League: its clubs and their display names. Nothing here is real."""

from types import MappingProxyType

CLUB_NAMES: MappingProxyType[str, str] = MappingProxyType(
    {
        "HCY": "Harbour City",
        "NGT": "Northgate FC",
        "KBA": "Kingsbridge Athletic",
        "ASV": "Ashford Vale",
        "CAL": "Calder Town",
        "WMR": "Westmere",
        "BRM": "Brackley Mills",
        "SLT": "Saltmarsh",
    }
)
LEAGUE_NAME = "Meridian League"
