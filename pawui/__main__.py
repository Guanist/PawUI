"""支持 ``python -m pawui app.paw``。"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
