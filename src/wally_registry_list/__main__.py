"""Entry point for Wally Registry List."""

from __future__ import annotations

import logging
import sys


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        from wally_registry_list.gui.app import WallyRegistryApp
    except ImportError as exc:
        print(
            "Failed to import GUI dependencies. Install with: pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    app = WallyRegistryApp()
    app.mainloop()


if __name__ == "__main__":
    main()
