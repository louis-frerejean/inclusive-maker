import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Union


def write_hand_state(state: str, target: Optional[Union[str, Path]] = None, source: str = "raspberry") -> dict:
    """Write the current hand state to a JSON file for the visual UI."""
    if target is None:
        target = Path(__file__).resolve().parent / "hand_state.json"
    else:
        target = Path(target)

    payload = {
        "state": state,
        "source": source,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return payload
