from flask import Blueprint, render_template, send_from_directory

main_routes = Blueprint("main_routes", __name__)


@main_routes.route("/")
def index():
    return render_template("index.html")


@main_routes.route("/favicon.ico")
def favicon():
    return send_from_directory("static/", "favicon.ico")


@main_routes.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static/", path)
