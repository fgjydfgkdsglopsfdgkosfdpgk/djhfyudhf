"""Entry point for running the Flask development server."""
from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(port=80, debug=True)
