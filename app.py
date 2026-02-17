from flask import Flask, render_template
from routes import api_routes
from datetime import datetime
from flask_sitemapper import Sitemapper
from keygen import generate_api_key

app = Flask(__name__, static_folder="static", static_url_path="")

sitemapper = Sitemapper()
sitemapper.init_app(app)

app.register_blueprint(api_routes)

app.config["SECRET_KEY"] = generate_api_key()


@app.context_processor
def inject_current_year():
    return dict(current_year=datetime.now().year)


@sitemapper.include(
    lastmod=datetime.now().strftime("%Y-%m-%d"),
    changefreq="daily",
    priority=1.0,
)
@app.route("/")
def home():
    return render_template("home.html")


@sitemapper.include(
    lastmod=datetime.now().strftime("%Y-%m-%d"), changefreq="daily", priority=0.8
)
@app.route("/docs")
@app.route("/documentation")
def docs():
    return render_template("docs.html")


@app.route("/sitemap.xml")
def sitemap():
    return sitemapper.generate()


if __name__ == "__main__":
    app.run(debug=True)
