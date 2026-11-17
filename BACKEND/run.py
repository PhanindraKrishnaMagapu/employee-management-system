"""Start the Flask application.

Run this from the BACKEND folder after installing requirements:

    python run.py

Phase 1 only boots the app. It does not expose business APIs.
"""

import sys


def main():
    try:
        from app import create_app
    except ModuleNotFoundError as exc:
        print(
            "Could not start the app. From the BACKEND folder, create a "
            "virtual environment and run: pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    app = create_app()
    # Debug reload is for local development. Waitress is used for deployment
    # in a later phase.
    app.run(host="127.0.0.1", port=5000, debug=True)


if __name__ == "__main__":
    main()
