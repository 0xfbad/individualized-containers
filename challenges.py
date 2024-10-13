import math
import json

from CTFd.models import db, Solves
from CTFd.plugins.challenges import BaseChallenge
from CTFd.utils.modes import get_model

from .models import ContainerChallengeModel
from .utils import get_settings_path

with open(get_settings_path(), 'r') as f:
    settings = json.load(f)

class ContainerChallenge(BaseChallenge):
    id = settings["plugin-info"]["id"]
    name = settings["plugin-info"]["name"]
    templates = settings["plugin-info"]["templates"]
    scripts = settings["plugin-info"]["scripts"]
    route = "/plugins/containers/assets/"

    challenge_model = ContainerChallengeModel

    @classmethod
    def read(cls, challenge):
        data = {
            "id": challenge.id,
            "name": challenge.name,
            "value": challenge.value,
            "image": challenge.image,
            "port": challenge.port,
            "command": challenge.command,
            "ctype": challenge.ctype,
            "ssh_username": challenge.ssh_username,
            "ssh_password": challenge.ssh_password,
            "initial": challenge.initial,
            "decay": challenge.decay,
            "minimum": challenge.minimum,
            "description": challenge.description,
            "connection_info": challenge.connection_info,
            "category": challenge.category,
            "state": challenge.state,
            "max_attempts": challenge.max_attempts,
            "type": challenge.type,
            "type_data": {
                "id": cls.id,
                "name": cls.name,
                "templates": cls.templates,
                "scripts": cls.scripts,
            },
        }
        return data

    @classmethod
    def calculate_value(cls, challenge):
        # get the current user or team model
        Model = get_model()

        # count the number of valid solves for the challenge
        solve_count = (
            Solves.query.join(Model, Solves.account_id == Model.id)
            .filter(
                Solves.challenge_id == challenge.id,
                Model.hidden == False,
                Model.banned == False,
            )
            .count()
        )

        # adjust solve count for calculation
        adjusted_solve_count = max(solve_count - 1, 0)

        # calculate the new challenge value based on decay formula
        value = (
            ((challenge.minimum - challenge.initial) / (challenge.decay ** 2))
            * (adjusted_solve_count ** 2)
        ) + challenge.initial

        value = math.ceil(value)

        if value < challenge.minimum:
            value = challenge.minimum

        # update the challenge value in the database
        challenge.value = value
        db.session.commit()

        return challenge

    @classmethod
    def update(cls, challenge, request):
        data = request.form or request.get_json() or {}

        # update challenge attributes with provided data
        for attr, value in data.items():
            # convert numeric fields to float if necessary
            if attr in ("initial", "minimum", "decay"):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    continue  # skip invalid numeric values
            setattr(challenge, attr, value)

        # recalculate the challenge value after update
        return cls.calculate_value(challenge)

    @classmethod
    def solve(cls, user, team, challenge, request):
        # call the parent solve method to register the solve
        super().solve(user, team, challenge, request)
        # recalculate the challenge value after a solve
        cls.calculate_value(challenge)
