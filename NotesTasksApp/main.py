import logging
import os
from services.controller import AppController
from ui.main_window import MainWindow


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("notes.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main() -> None:
    configure_logging()
    controller = AppController(num_workers=4)
    default_json = os.path.join("data", "notes.json")
    if os.path.exists(default_json):
        controller.start_background_import(default_json)
    app = MainWindow(controller)
    app.mainloop()


if __name__ == "__main__":
    main()
