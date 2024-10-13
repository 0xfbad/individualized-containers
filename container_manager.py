import atexit
import time
import json
import random
import socket

from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers import SchedulerNotRunningError
import docker
import paramiko
import requests

from CTFd.models import db
from .models import ContainerInfoModel


class ContainerException(Exception):
    def __init__(self, *args):
        super().__init__(*args)
        self.message = args[0] if args else "unknown container exception"

    def __str__(self):
        return self.message


class ContainerManager:
    def __init__(self, settings, app):
        self.settings = settings
        self.app = app
        self.client = None

        docker_base_url = settings.get("docker_base_url", "")
        if not docker_base_url:
            return

        # initialize docker client
        try:
            self.initialize_connection()
        except ContainerException:
            print("docker could not initialize or connect.")

    def initialize_connection(self):
        # shut down existing scheduler if running
        try:
            self.expiration_scheduler.shutdown()
        except (SchedulerNotRunningError, AttributeError):
            pass  # scheduler was never running

        docker_base_url = self.settings.get("docker_base_url", "")
        if not docker_base_url:
            self.client = None
            return

        # initialize docker client
        try:
            self.client = docker.DockerClient(base_url=docker_base_url)
            self.client.ping()
        except (
            docker.errors.DockerException,
            paramiko.ssh_exception.SSHException,
            requests.exceptions.RequestException,
        ) as e:
            self.client = None
            raise ContainerException(f"could not connect to docker: {e}")

        # set up container expiration scheduler
        try:
            self.expiration_seconds = int(self.settings.get("container_expiration", 0)) * 60
        except (ValueError, TypeError):
            self.expiration_seconds = 0

        if self.expiration_seconds > 0:
            self.setup_expiration_scheduler()

    def setup_expiration_scheduler(self):
        expiration_check_interval = 5  # seconds

        # initialize the background scheduler
        self.expiration_scheduler = BackgroundScheduler()
        self.expiration_scheduler.add_job(
            func=self.kill_expired_containers,
            args=(self.app,),
            trigger="interval",
            seconds=expiration_check_interval,
        )
        self.expiration_scheduler.start()

        # ensure scheduler shuts down when app exits
        atexit.register(lambda: self.expiration_scheduler.shutdown())

    def _is_port_available(self, port: int) -> bool:
        # check if a given port is available for binding
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            try:
                s.bind(("0.0.0.0", port))
                return True
            except OSError:
                return False

    def run_command(func):
        # decorator to ensure docker client is connected before running a command
        def wrapper(self, *args, **kwargs):
            if self.client is None:
                try:
                    self.initialize_connection()
                except ContainerException:
                    raise ContainerException("docker is not connected")

            try:
                self.client.ping()
            except (docker.errors.DockerException, requests.exceptions.RequestException):
                try:
                    self.initialize_connection()
                except ContainerException:
                    pass
                raise ContainerException("docker connection was lost. please try your request again later.")

            return func(self, *args, **kwargs)
        return wrapper

    @run_command
    def kill_expired_containers(self, app: Flask):
        # kill containers that have expired
        with app.app_context():
            containers = ContainerInfoModel.query.all()
            for container in containers:
                if container.expires < int(time.time()):
                    try:
                        self.kill_container(container.container_id)
                    except ContainerException:
                        print("[container expiry job] docker is not initialized. please check your settings.")
                    db.session.delete(container)
                    db.session.commit()

    @run_command
    def is_container_running(self, container_id: str) -> bool:
        # check if a container is currently running
        try:
            container = self.client.containers.get(container_id)
            return container.status == "running"
        except docker.errors.NotFound:
            return False
        except docker.errors.DockerException as e:
            raise ContainerException(f"docker error: {e}")

    @run_command
    def create_container(
        self,
        chal_id: str,
        team_id: str,
        user_id: str,
        image: str,
        port: int,
        command: str,
        volumes: str,
    ):
        # create and start a new container
        kwargs = {}

        # set memory limit if specified
        mem_limit = self.settings.get("container_maxmemory")
        if mem_limit:
            try:
                mem_limit = int(mem_limit)
                if mem_limit > 0:
                    kwargs["mem_limit"] = f"{mem_limit}m"
            except ValueError:
                raise ContainerException("configured container memory limit must be an integer")

        # set cpu limit if specified
        cpu_limit = self.settings.get("container_maxcpu")
        if cpu_limit:
            try:
                cpu_quota = float(cpu_limit)
                if cpu_quota > 0:
                    kwargs["cpu_quota"] = int(cpu_quota * 100000)
                    kwargs["cpu_period"] = 100000
                else:
                    raise ValueError
            except ValueError:
                raise ContainerException("configured container cpu limit must be a positive number")

        # set volumes if specified
        if volumes:
            try:
                volumes_dict = json.loads(volumes)
                kwargs["volumes"] = volumes_dict
            except json.decoder.JSONDecodeError:
                raise ContainerException("volumes json string is invalid")

        # find an available external port
        external_port = port
        max_tries = 100
        for _ in range(max_tries):
            if self._is_port_available(external_port):
                break
            external_port = random.randint(port, 65535)
        else:
            raise ContainerException("no available port found")

        # create the container
        try:
            return self.client.containers.run(
                image,
                ports={str(port): str(external_port)},
                command=command,
                detach=True,
                auto_remove=True,
                environment={
                    "CHALLENGE_ID": chal_id,
                    "TEAM_ID": team_id,
                    "USER_ID": user_id,
                },
                **kwargs,
            )
        except docker.errors.ImageNotFound:
            raise ContainerException("docker image not found")
        except docker.errors.DockerException as e:
            raise ContainerException(f"docker error: {e}")

    @run_command
    def get_container_port(self, container_id: str) -> str:
        # get the host port mapped to the container's exposed port
        try:
            container = self.client.containers.get(container_id)
            ports = container.attrs["NetworkSettings"]["Ports"]
            for port_mappings in ports.values():
                if port_mappings:
                    return port_mappings[0]["HostPort"]
        except (KeyError, IndexError, docker.errors.NotFound):
            return None
        except docker.errors.DockerException as e:
            raise ContainerException(f"docker error: {e}")
        return None

    @run_command
    def get_images(self) -> list:
        # retrieve a list of available docker images
        try:
            images = self.client.images.list()
            images_list = [tag for image in images for tag in image.tags if tag]
            return sorted(images_list)
        except docker.errors.DockerException as e:
            raise ContainerException(f"docker error: {e}")
        return []

    @run_command
    def kill_container(self, container_id: str):
        # kill and remove a container by its id
        try:
            container = self.client.containers.get(container_id)
            container.kill()
        except docker.errors.NotFound:
            pass  # container already removed
        except docker.errors.DockerException as e:
            raise ContainerException(f"docker error: {e}")

    def is_connected(self) -> bool:
        # check if docker client is connected
        if not self.client:
            return False

        try:
            self.client.ping()
            return True
        except docker.errors.DockerException:
            return False
