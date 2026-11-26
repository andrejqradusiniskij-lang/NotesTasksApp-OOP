import logging
import os
import sys
from services.controller import AppController
from ui.main_window import MainWindow


def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resolve_default_json() -> str:
    external_path = os.path.join(get_base_dir(), "data", "notes.json")
    if os.path.exists(external_path):
        return external_path
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled_path = os.path.join(meipass, "data", "notes.json")
        if os.path.exists(bundled_path):
            return bundled_path
    return os.path.join("data", "notes.json")


def configure_logging() -> None:
    log_path = os.path.join(get_base_dir(), "notes.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main() -> None:
    configure_logging()
    controller = AppController(num_workers=4)
    default_json = resolve_default_json()
    if os.path.exists(default_json):
        controller.start_background_import(default_json)
    app = MainWindow(controller)
    app.mainloop()


if __name__ == "__main__":
    main()