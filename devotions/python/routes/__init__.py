"""Route modules for the devotions Flask app.

Each module exposes ``register(app, **deps)``, which attaches its route
handlers to the given Flask app with plain ``@app.route(...)`` calls.
Blueprints are deliberately NOT used: they prefix endpoint names, and the
templates call url_for() with the bare endpoint names registered here.
main.py imports these modules at the end of its own setup (the app object,
OAuth client, and decorators must exist first) and calls each register()
with the dependencies its handlers need.
"""
