from flask import (
	request, render_template, flash, redirect, url_for, current_app, jsonify
)
from CTFd.utils.decorators import admins_only
from CTFd.models import db

from . import containers_bp
from .helpers import kill_container
from ..utils import settings_to_dict, is_team_mode
from ..models import ContainerInfoModel, ContainerSettingsModel
from ..container_manager import ContainerException

# route to display the containers dashboard
@containers_bp.route("/dashboard", methods=["GET"])
@admins_only
def route_containers_dashboard():
	container_manager = current_app.container_manager
	running_containers = ContainerInfoModel.query.order_by(
		ContainerInfoModel.timestamp.desc()
	).all()

	try:
		connected = container_manager.is_connected()
	except ContainerException:
		connected = False

	# update each container's running status
	for container in running_containers:
		try:
			container.is_running = container_manager.is_container_running(
				container.container_id
			)
		except ContainerException:
			container.is_running = False

	return render_template(
		"container_dashboard.html",
		containers=running_containers,
		connected=connected,
	)

# api route to get running containers data
@containers_bp.route("/api/running_containers", methods=["GET"])
@admins_only
def route_get_running_containers():
	container_manager = current_app.container_manager
	running_containers = ContainerInfoModel.query.order_by(
		ContainerInfoModel.timestamp.desc()
	).all()

	try:
		connected = container_manager.is_connected()
	except ContainerException:
		connected = False

	unique_teams = set()
	unique_challenges = set()
	team_mode = is_team_mode()

	# collect unique teams and challenges
	for container in running_containers:
		try:
			container.is_running = container_manager.is_container_running(
				container.container_id
			)
		except ContainerException:
			container.is_running = False

		if team_mode:
			unique_teams.add(f"{container.team.name} [{container.team_id}]")
		else:
			unique_teams.add(f"{container.user.name} [{container.user_id}]")
		unique_challenges.add(f"{container.challenge.name} [{container.challenge_id}]")

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
		if team_mode:
			container_data["team"] = f"{container.team.name} [{container.team_id}]"
		running_containers_data.append(container_data)

	response_data = {
		"containers": running_containers_data,
		"connected": connected,
		"teams": list(unique_teams),
		"challenges": list(unique_challenges),
	}

	return jsonify(response_data)

# api route to kill a specific container
@containers_bp.route("/api/kill", methods=["POST"])
@admins_only
def route_kill_container():
	if not request.is_json:
		return jsonify(error="invalid request"), 400

	container_id = request.json.get("container_id")
	if not container_id:
		return jsonify(error="no container_id specified"), 400

	result = kill_container(container_id)
	status_code = 200 if 'success' in result else 400
	return jsonify(result), status_code

# api route to purge all containers
@containers_bp.route("/api/purge", methods=["POST"])
@admins_only
def route_purge_containers():
	containers = ContainerInfoModel.query.all()
	for container in containers:
		try:
			kill_container(container.container_id)
		except ContainerException:
			pass
	return jsonify(success="purged all containers"), 200

# api route to get available docker images
@containers_bp.route("/api/images", methods=["GET"])
@admins_only
def route_get_images():
	container_manager = current_app.container_manager
	try:
		images = container_manager.get_images()
	except ContainerException as err:
		return jsonify(error=str(err)), 500

	return jsonify(images=images)

# api route to update container settings
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
		if not request.form.get(field):
			flash(f"missing required field: {field}", "error")
			return redirect(url_for(".route_containers_settings"))

	# update or create settings in the database
	for field in required_fields:
		setting = ContainerSettingsModel.query.filter_by(key=field).first()
		if not setting:
			setting = ContainerSettingsModel(key=field, value=request.form.get(field))
			db.session.add(setting)
		else:
			setting.value = request.form.get(field)

	db.session.commit()

	# re-initialize container manager with new settings
	container_manager.settings = settings_to_dict(ContainerSettingsModel.query.all())

	if container_manager.settings.get("docker_base_url"):
		try:
			container_manager.initialize_connection()
		except ContainerException as err:
			flash(str(err), "error")
			return redirect(url_for(".route_containers_settings"))

	return redirect(url_for(".route_containers_dashboard"))

# route to display the container settings page
@containers_bp.route("/settings", methods=["GET"])
@admins_only
def route_containers_settings():
	container_manager = current_app.container_manager
    
	return render_template(
		"container_settings.html", settings=container_manager.settings
	)
