"""Legacy compatibility shim.

Use `run_lsr7_controller.py` for the current JBL 7 Series controller.
This file is intentionally kept only so older shortcuts still launch the
same speaker-first application.
"""

from lsr7_gui import main


if __name__ == "__main__":
    main()
