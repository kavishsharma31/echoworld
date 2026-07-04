from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

# Cognee reads provider configuration during import, so load .env first.
import cognee


_COGNEE_CONNECTED = False


async def ensure_cognee_connected() -> None:
    global _COGNEE_CONNECTED

    use_cognee_cloud = os.getenv("USE_COGNEE_CLOUD", "").strip().casefold()
    if use_cognee_cloud != "true":
        return
    if _COGNEE_CONNECTED:
        return

    service_url = os.getenv("COGNEE_SERVICE_URL", "").strip()
    api_key = os.getenv("COGNEE_API_KEY", "").strip()
    missing = [
        name
        for name, value in (
            ("COGNEE_SERVICE_URL", service_url),
            ("COGNEE_API_KEY", api_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Cognee Cloud is enabled, but required configuration is missing: "
            + ", ".join(missing)
        )

    await cognee.serve(url=service_url, api_key=api_key)
    _COGNEE_CONNECTED = True
    print("Cognee Cloud connected.")
