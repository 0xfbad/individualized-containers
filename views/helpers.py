import time
import json
import datetime
from flask import current_app
from CTFd.models import db

from . import containers_bp
from ..models import ContainerInfoModel, ContainerChallengeModel
from ..container_manager import ContainerException
from ..utils import settings

# function to kill a container by its id
def kill_container(container_id):
    container_manager = current_app.container_manager
    container = ContainerInfoModel.query.filter_by(container_id=container_id).first()

    try:
        container_manager.kill_container(container_id)
    except ContainerException:
        return {"error": "docker is not initialized. please check your settings."}

    if container:
        db.session.delete(container)
        db.session.commit()
        return {"success": "container killed"}
    else:
        return {"error": "container not found"}

# function to renew an existing container's expiration time
def renew_container(chal_id, xid, is_team):
    container_manager = current_app.container_manager
    challenge = ContainerChallengeModel.query.filter_by(id=chal_id).first()

    # check if the challenge exists
    if challenge is None:
        return {"error": "challenge not found"}, 400

    # determine whether to filter by team_id or user_id
    filter_args = {'challenge_id': challenge.id}
    filter_args['team_id' if is_team else 'user_id'] = xid
    running_container = ContainerInfoModel.query.filter_by(**filter_args).first()

    # check if there is a running container
    if running_container is None:
        return {"error": "container not found, try resetting the container."}

    try:
        # update the container's expiration time
        running_container.expires = int(time.time() + container_manager.expiration_seconds)
        db.session.commit()
    except Exception:
        return {"error": "database error occurred, please try again."}

    # return the updated container details
    return {
        "success": "container renewed",
        "expires": running_container.expires,
        "hostname": container_manager.settings.get("docker_hostname", ""),
        "ssh_username": challenge.ssh_username,
        "ssh_password": challenge.ssh_password,
        "port": running_container.port,
        "connect": challenge.ctype,
    }

# function to create a new container for a challenge
def create_container(chal_id, xid, uid, is_team):
    container_manager = current_app.container_manager
    challenge = ContainerChallengeModel.query.filter_by(id=chal_id).first()

    # check if the challenge exists
    if challenge is None:
        return {"error": "challenge not found"}, 400

    # get the maximum number of allowed containers
    max_containers_allowed = int(settings["vars"]["MAX_CONTAINERS_ALLOWED"])
    if not is_team:
        uid = xid
    user_containers = ContainerInfoModel.query.filter_by(user_id=uid)

    # check if the user has reached the maximum allowed containers
    if user_containers.count() >= max_containers_allowed:
        return {
            "error": f"you can only spawn {max_containers_allowed} containers at a time. please stop other containers to continue"
        }, 500

    # check for any existing containers for the user/team and challenge
    filter_args = {'challenge_id': challenge.id}
    filter_args['team_id' if is_team else 'user_id'] = xid
    running_container = ContainerInfoModel.query.filter_by(**filter_args).first()

    if running_container:
        try:
            if container_manager.is_container_running(running_container.container_id):
                # return existing container details
                return json.dumps({
                    "status": "already_running",
                    "hostname": container_manager.settings.get("docker_hostname", ""),
                    "port": running_container.port,
                    "ssh_username": challenge.ssh_username,
                    "ssh_password": challenge.ssh_password,
                    "connect": challenge.ctype,
                    "expires": running_container.expires,
                })
            else:
                # remove the container from the database if it's not running
                db.session.delete(running_container)
                db.session.commit()
        except ContainerException as err:
            return {"error": str(err)}, 500

    # try to create a new container
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

    # get the port assigned to the new container
    port = container_manager.get_container_port(created_container.id)

    if port is None:
        return json.dumps({"status": "error", "error": "could not get port"})

    expires = int(time.time() + container_manager.expiration_seconds)

    # add the new container to the database
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

    # return new container details
    return json.dumps({
        "status": "created",
        "hostname": container_manager.settings.get("docker_hostname", ""),
        "port": port,
        "ssh_username": challenge.ssh_username,
        "ssh_password": challenge.ssh_password,
        "connect": challenge.ctype,
        "expires": expires,
    })

# function to view information about a container
def view_container_info(chal_id, xid, is_team):
    container_manager = current_app.container_manager
    challenge = ContainerChallengeModel.query.filter_by(id=chal_id).first()

    # check if the challenge exists
    if challenge is None:
        return {"error": "challenge not found"}, 400

    # check for any existing containers for the user/team and challenge
    filter_args = {'challenge_id': challenge.id}
    filter_args['team_id' if is_team else 'user_id'] = xid
    running_container = ContainerInfoModel.query.filter_by(**filter_args).first()

    if running_container:
        try:
            if container_manager.is_container_running(running_container.container_id):
                # return existing container details
                return json.dumps({
                    "status": "already_running",
                    "hostname": container_manager.settings.get("docker_hostname", ""),
                    "port": running_container.port,
                    "ssh_username": challenge.ssh_username,
                    "ssh_password": challenge.ssh_password,
                    "connect": challenge.ctype,
                    "expires": running_container.expires,
                })
            else:
                # remove the container from the database if it's not running
                db.session.delete(running_container)
                db.session.commit()
        except ContainerException as err:
            return {"error": str(err)}, 500
    else:
        return {"status": "instance not started"}

# function to get the connection type of a challenge
def connect_type(chal_id):
    challenge = ContainerChallengeModel.query.filter_by(id=chal_id).first()

    # check if the challenge exists
    if challenge is None:
        return {"error": "challenge not found"}, 400

    return json.dumps({"status": "ok", "connect": challenge.ctype})

# filter to format unix timestamp into a readable time string
@containers_bp.app_template_filter("format_time")
def format_time_filter(unix_seconds):
    dt = datetime.datetime.fromtimestamp(
        unix_seconds,
        tz=datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo,
    )

    return dt.strftime("%H:%M:%S %d/%m/%Y")
