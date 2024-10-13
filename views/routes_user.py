from flask import request, current_app
from CTFd.utils.decorators import (
    authed_only,
    during_ctf_time_only,
    ratelimit,
    require_verified_emails,
)
from CTFd.utils.user import get_current_user

from . import containers_bp
from ..utils import is_team_mode, settings
from .helpers import (
    connect_type,
    view_container_info,
    create_container,
    renew_container,
    kill_container,
)
from ..container_manager import ContainerException
from ..models import ContainerInfoModel


@containers_bp.route("/api/get_connect_type/<int:challenge_id>", methods=["GET"])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(
    method="GET",
    limit=settings["requests"]["limit"],
    interval=settings["requests"]["interval"],
)
def get_connect_type_route(challenge_id):
    try:
        return connect_type(challenge_id)
    except ContainerException as err:
        return {"error": str(err)}, 500


@containers_bp.route("/api/view_info", methods=["POST"])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(
    method="POST",
    limit=settings["requests"]["limit"],
    interval=settings["requests"]["interval"],
)
def route_view_info():
    user = get_current_user()

    # Validate the request
    if request.json is None:
        return {"error": "Invalid request"}, 400

    chal_id = request.json.get("chal_id")
    if chal_id is None:
        return {"error": "No chal_id specified"}, 400

    if user is None:
        return {"error": "User not found"}, 400
    if user.team is None and is_team_mode():
        return {"error": "User not a member of a team"}, 400

    try:
        if is_team_mode():
            return view_container_info(chal_id, user.team.id, True)
        else:
            return view_container_info(chal_id, user.id, False)
    except ContainerException as err:
        return {"error": str(err)}, 500


@containers_bp.route("/api/request", methods=["POST"])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(
    method="POST",
    limit=settings["requests"]["limit"],
    interval=settings["requests"]["interval"],
)
def route_request_container():
    user = get_current_user()

    # Validate the request
    if request.json is None:
        return {"error": "Invalid request"}, 400

    chal_id = request.json.get("chal_id")
    if chal_id is None:
        return {"error": "No chal_id specified"}, 400

    if user is None:
        return {"error": "User not found"}, 400
    if user.team is None and is_team_mode():
        return {"error": "User not a member of a team"}, 400

    try:
        if is_team_mode():
            return create_container(chal_id, user.team.id, user.id, True)
        else:
            return create_container(chal_id, user.id, user.id, False)
    except ContainerException as err:
        return {"error": str(err)}, 500


@containers_bp.route("/api/renew", methods=["POST"])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(
    method="POST",
    limit=settings["requests"]["limit"],
    interval=settings["requests"]["interval"],
)
def route_renew_container_route():
    user = get_current_user()

    # Validate the request
    if request.json is None:
        return {"error": "Invalid request"}, 400

    chal_id = request.json.get("chal_id")
    if chal_id is None:
        return {"error": "No chal_id specified"}, 400

    if user is None:
        return {"error": "User not found"}, 400
    if user.team is None and is_team_mode():
        return {"error": "User not a member of a team"}, 400

    try:
        if is_team_mode():
            return renew_container(chal_id, user.team.id, True)
        else:
            return renew_container(chal_id, user.id, False)
    except ContainerException as err:
        return {"error": str(err)}, 500


@containers_bp.route("/api/stop", methods=["POST"])
@authed_only
@during_ctf_time_only
@require_verified_emails
@ratelimit(
    method="POST",
    limit=settings["requests"]["limit"],
    interval=settings["requests"]["interval"],
)
def route_stop_container():
    user = get_current_user()

    # Validate the request
    if request.json is None:
        return {"error": "Invalid request"}, 400

    chal_id = request.json.get("chal_id")
    if chal_id is None:
        return {"error": "No chal_id specified"}, 400

    if user is None:
        return {"error": "User not found"}, 400
    if user.team is None and is_team_mode():
        return {"error": "User not a member of a team"}, 400

    if is_team_mode():
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=chal_id, team_id=user.team.id
        ).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=chal_id, user_id=user.id
        ).first()

    if running_container:
        return kill_container(running_container.container_id)
    else:
        return {"error": "No container found"}, 400
