
import sys
from pathlib import Path

from waitress import serve

# Locate the project root inside the Docker container.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Make the existing Azure modules importable.
sys.path.insert(
    0,
    str(PROJECT_ROOT / "backend" / "azure")
)

# Load the original Flask History + Control API.
from backend.azure.history_api import app
from backend.api import control_api


if __name__ == "__main__":

    print("[API] Starting Flask History + Control API")

    # Start the existing MQTT control listener.
    control_api.start_control_mqtt()

    try:
        # Make the API reachable through Docker port mapping.
        serve(
            app,
            host="0.0.0.0",
            port=5001,
            threads=4,
        )

    finally:
        control_api.stop_control_mqtt()
