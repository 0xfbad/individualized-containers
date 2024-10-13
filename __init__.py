from flask import Flask
from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES

from .challenges import ContainerChallenge
from .models import ContainerSettingsModel
from .utils import settings_to_dict
from .container_manager import ContainerManager
from .views import containers_bp

def load(app: Flask):
    app.db.create_all()
    CHALLENGE_CLASSES["container"] = ContainerChallenge
    register_plugin_assets_directory(app, base_path="/plugins/containers/assets/")

    # Load container settings from the database
    container_settings = settings_to_dict(ContainerSettingsModel.query.all())
    container_manager = ContainerManager(container_settings, app)

    # Store the container_manager in the app context
    app.container_manager = container_manager

    # Register the blueprint
    app.register_blueprint(containers_bp)
