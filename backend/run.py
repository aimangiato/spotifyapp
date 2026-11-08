import os
from backend import create_app

app = create_app()

if __name__ == "__main__":
    is_debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="127.0.0.1", port=port, debug=is_debug)
