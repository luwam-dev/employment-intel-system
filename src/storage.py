from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def save_results_to_excel(output_file: Path, results: list[dict[str, Any]]) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)

    try:
        df.to_excel(output_file, index=False)
        return output_file
    except PermissionError:
        fallback = output_file.with_name("enriched_autosave.xlsx")
        df.to_excel(fallback, index=False)
        print(f"   Excel file is open. Saved instead to {fallback}")
        return fallback