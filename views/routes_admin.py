import json

from flask import request, render_template, flash, redirect, url_for, current_app
from CTFd.utils.decorators import admins_only
from CTFd.models import db

from . import containers_bp
from ..utils import settings_to_dict, is_team_mode
from .helpers import kill_container
from ..models import ContainerInfoModel, ContainerSettingsModel
from ..container_manager import ContainerException


@containers_bp.route("/dashboard", methods=["GET"])
@admins_only
def route_containers_dashboard():
    container_manager = current_app.container_manager
    running_containers = ContainerInfoModel.query.order_by(
        ContainerInfoModel.timestamp.desc()
    ).all()

    connected = False
    try:
        connected = container_manager.is_connected()
    except ContainerException:
        pass

    for i, container in enumerate(running_containers):
        try:
            running_containers[i].is_running = container_manager.is_container_running(
                container.container_id
            )
        except ContainerException:
            running_containers[i].is_running = False

    return render_template(
        "container_dashboard.html",
        containers=running_containers,
        connected=connected,
    )


@containers_bp.route("/api/running_containers", methods=["GET"])
@admins_only
def route_get_running_containers():
    container_manager = current_app.container_manager
    running_containers = ContainerInfoModel.query.order_by(
        ContainerInfoModel.timestamp.desc()
    ).all()

    connected = False
    try:
        connected = container_manager.is_connected()
    except ContainerException:
        pass

    # Create lists to store unique teams and challenges
    unique_teams = set()
    unique_challenges = set()

    for i, container in enumerate(running_containers):
        try:
            running_containers[i].is_running = container_manager.is_container_running(
                container.container_id
            )
        except ContainerException:
            running_containers[i].is_running = False

        # Add team and challenge to the unique sets
        if is_team_mode():
            unique_teams.add(f"{container.team.name} [{container.team_id}]")
        else:
            unique_teams.add(f"{container.user.name} [{container.user_id}]")
        unique_challenges.add(
            f"{container.challenge.name} [{container.challenge_id}]"
        )

    # Convert unique sets to lists
    unique_teams_list = list(unique_teams)
    unique_challenges_list = list(unique_challenges)

    # Create a list of dictionaries containing running_containers data
    running_containers_data = []
    for container in running_containers:
        container_data = {
            "container_id": container.container_id,
            "image": container.challenge.image,
            "challenge": f"{container.challenge.name} [{container.challenge_id}]",
            "user": f"{container.user.name} [{container.user_id}]",
            "port": container.port,
            "created": container.timestamp,
            "expires": container.expires,
            "is_running": container.is_running,
        }
        if is_team_mode():
            container_data["team"] = f"{container.team.name} [{container.team_id}]"
        running_containers_data.append(container_data)

    # Create a JSON response containing running_containers_data, unique teams, and unique challenges
    response_data = {
        "containers": running_containers_data,
        "connected": connected,
        "teams": unique_teams_list,
        "challenges": unique_challenges_list,
    }

    # Return the JSON response
    return json.dumps(response_data)


@containers_bp.route("/api/kill", methods=["POST"])
@admins_only
def route_kill_container():
    if request.json is None:
        return {"error": "Invalid request"}, 400

    container_id = request.json.get("container_id")
    if container_id is None:
        return {"error": "No container_id specified"}, 400

    return kill_container(container_id)


@containers_bp.route("/api/purge", methods=["POST"])
@admins_only
def route_purge_containers():
    containers = ContainerInfoModel.query.all()
    for container in containers:
        try:
            kill_container(container.container_id)
        except ContainerException:
            pass
    return {"success": "Purged all containers"}, 200


@containers_bp.route("/api/images", methods=["GET"])
@admins_only
def route_get_images():
    container_manager = current_app.container_manager
    try:
        images = container_manager.get_images()
    except ContainerException as err:
        return {"error": str(err)}

    return {"images": images}


@containers_bp.route("/api/settings/update", methods=["POST"])
@admins_only
def route_update_settings():
    container_manager = current_app.container_manager

    required_fields = [
        "docker_base_url",
        "docker_hostname",
        "container_expiration",
        "container_maxmemory",
        "container_maxcpu",
    ]

    for field in required_fields:
        if request.form.get(field) is None:
            return {"error": f"Missing required field: {field}"}, 400

    # Update or create settings in the database
    for field in required_fields:
        setting = ContainerSettingsModel.query.filter_by(key=field).first()
        if setting is None:
            setting = ContainerSettingsModel(key=field, value=request.form.get(field))
            db.session.add(setting)
        else:
            setting.value = request.form.get(field)

    db.session.commit()

    # Update settings in the container manager
    container_manager.settings = settings_to_dict(ContainerSettingsModel.query.all())

    if container_manager.settings.get("docker_base_url") is not None:
        try:
            container_manager.initialize_connection(container_manager.settings)
        except ContainerException as err:
            flash(str(err), "error")
            return redirect(url_for(".route_containers_settings"))

    return redirect(url_for(".route_containers_dashboard"))


@containers_bp.route("/settings", methods=["GET"])
@admins_only
def route_containers_settings():
    container_manager = current_app.container_manager
    return render_template(
        "container_settings.html", settings=container_manager.settings
    )
