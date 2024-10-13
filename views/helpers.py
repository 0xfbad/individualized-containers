import time
import json
import datetime
from flask import current_app
from CTFd.models import db
from CTFd.utils import get_config

from . import containers_bp
from ..models import ContainerInfoModel, ContainerChallengeModel
from ..container_manager import ContainerException
from ..utils import settings


def kill_container(container_id):
    container_manager = current_app.container_manager
    container = ContainerInfoModel.query.filter_by(container_id=container_id).first()

    try:
        container_manager.kill_container(container_id)
    except ContainerException:
        return {"error": "Docker is not initialized. Please check your settings."}

    if container:
        db.session.delete(container)
        db.session.commit()
        return {"success": "Container killed"}
    else:
        return {"error": "Container not found"}


def renew_container(chal_id, xid, is_team):
    container_manager = current_app.container_manager

    # Get the requested challenge
    challenge = ContainerChallengeModel.query.filter_by(id=chal_id).first()

    # Make sure the challenge exists
    if challenge is None:
        return {"error": "Challenge not found"}, 400

    # Fetch the running container
    if is_team:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, team_id=xid
        ).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, user_id=xid
        ).first()

    if running_container is None:
        return {"error": "Container not found, try resetting the container."}

    try:
        running_container.expires = int(
            time.time() + container_manager.expiration_seconds
        )
        db.session.commit()
    except ContainerException:
        return {"error": "Database error occurred, please try again."}

    return {
        "success": "Container renewed",
        "expires": running_container.expires,
        "hostname": container_manager.settings.get("docker_hostname", ""),
        "ssh_username": challenge.ssh_username,
        "ssh_password": challenge.ssh_password,
        "port": running_container.port,
        "connect": challenge.ctype,
    }


def create_container(chal_id, xid, uid, is_team):
    container_manager = current_app.container_manager

    # Get the requested challenge
    challenge = ContainerChallengeModel.query.filter_by(id=chal_id).first()

    # Make sure the challenge exists
    if challenge is None:
        return {"error": "Challenge not found"}, 400

    # Check if user already has MAX_CONTAINERS_ALLOWED number of running containers.
    MAX_CONTAINERS_ALLOWED = int(settings["vars"]["MAX_CONTAINERS_ALLOWED"])
    if not is_team:
        uid = xid
    t_containers = ContainerInfoModel.query.filter_by(user_id=uid)

    if t_containers.count() >= MAX_CONTAINERS_ALLOWED:
        return {
            "error": f"You can only spawn {MAX_CONTAINERS_ALLOWED} containers at a time. Please stop other containers to continue"
        }, 500

    # Check for any existing containers for the user/team and challenge
    if is_team:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, team_id=xid
        ).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, user_id=xid
        ).first()

    # If a container is already running, return it
    if running_container:
        try:
            if container_manager.is_container_running(running_container.container_id):
                return json.dumps(
                    {
                        "status": "already_running",
                        "hostname": container_manager.settings.get(
                            "docker_hostname", ""
                        ),
                        "port": running_container.port,
                        "ssh_username": challenge.ssh_username,
                        "ssh_password": challenge.ssh_password,
                        "connect": challenge.ctype,
                        "expires": running_container.expires,
                    }
                )
            else:
                # Container is not running, remove it from the database
                db.session.delete(running_container)
                db.session.commit()
        except ContainerException as err:
            return {"error": str(err)}, 500

    # Run a new Docker container
    try:
        created_container = container_manager.create_container(
            chal_id,
            xid,
            uid,
            challenge.image,
            challenge.port,
            challenge.command,
            challenge.volumes,
        )
    except ContainerException as err:
        return {"error": str(err)}

    # Fetch the random port Docker assigned
    port = container_manager.get_container_port(created_container.id)

    # Port may be blank if the container failed to start
    if port is None:
        return json.dumps({"status": "error", "error": "Could not get port"})

    expires = int(time.time() + container_manager.expiration_seconds)

    # Insert the new container into the database
    new_container = ContainerInfoModel(
        container_id=created_container.id,
        challenge_id=challenge.id,
        team_id=xid if is_team else None,
        user_id=uid,
        port=port,
        timestamp=int(time.time()),
        expires=expires,
    )
    db.session.add(new_container)
    db.session.commit()

    return json.dumps(
        {
            "status": "created",
            "hostname": container_manager.settings.get("docker_hostname", ""),
            "port": port,
            "ssh_username": challenge.ssh_username,
            "ssh_password": challenge.ssh_password,
            "connect": challenge.ctype,
            "expires": expires,
        }
    )


def view_container_info(chal_id, xid, is_team):
    container_manager = current_app.container_manager

    # Get the requested challenge
    challenge = ContainerChallengeModel.query.filter_by(id=chal_id).first()

    # Make sure the challenge exists
    if challenge is None:
        return {"error": "Challenge not found"}, 400

    # Check for any existing containers for the user/team and challenge
    if is_team:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, team_id=xid
        ).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge.id, user_id=xid
        ).first()

    # If a container is already running, return it
    if running_container:
        try:
            if container_manager.is_container_running(running_container.container_id):
                return json.dumps(
                    {
                        "status": "already_running",
                        "hostname": container_manager.settings.get(
                            "docker_hostname", ""
                        ),
                        "port": running_container.port,
                        "ssh_username": challenge.ssh_username,
                        "ssh_password": challenge.ssh_password,
                        "connect": challenge.ctype,
                        "expires": running_container.expires,
                    }
                )
            else:
                # Container is not running, remove it from the database
                db.session.delete(running_container)
                db.session.commit()
        except ContainerException as err:
            return {"error": str(err)}, 500
    else:
        return {"status": "Instance not started"}


def connect_type(chal_id):
    # Get the requested challenge
    challenge = ContainerChallengeModel.query.filter_by(id=chal_id).first()

    # Make sure the challenge exists
    if challenge is None:
        return {"error": "Challenge not found"}, 400

    return json.dumps({"status": "Ok", "connect": challenge.ctype})

@containers_bp.app_template_filter("format_time")
def format_time_filter(unix_seconds):
    dt = datetime.datetime.fromtimestamp(
        unix_seconds,
        tz=datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo,
    )
    return dt.strftime("%H:%M:%S %d/%m/%Y")
