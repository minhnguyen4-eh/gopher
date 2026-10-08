"""Entry point: `python -m gopher` or the `gopher` console script."""

from gopher.core.controller import Controller
from gopher.ui.menubar import MenubarApp


def main():
    MenubarApp(Controller()).run()


if __name__ == "__main__":
    main()
