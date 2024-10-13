
from flask import Blueprint
import os

# Get the absolute path to the templates directory
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(current_dir, '..', 'templates')

containers_bp = Blueprint(
    "containers",
    __name__,
    template_folder=templates_dir,
    static_folder="assets",
    url_prefix="/containers",
)

from . import routes_user
from . import routes_admin
from . import helpers


