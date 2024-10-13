from sqlalchemy.orm import relationship
from CTFd.models import db, Challenges

class ContainerChallengeModel(Challenges):
	__tablename__ = 'container_challenges'
	__mapper_args__ = {'polymorphic_identity': 'container'}
	id = db.Column(
		db.Integer,
		db.ForeignKey('challenges.id', ondelete='CASCADE'),
		primary_key=True
	)
	image = db.Column(db.Text)
	port = db.Column(db.Integer)
	command = db.Column(db.Text, default='')
	volumes = db.Column(db.Text, default='')
	ctype = db.Column(db.Text, default='tcp')
	ssh_username = db.Column(db.Text, nullable=True)
	ssh_password = db.Column(db.Text, nullable=True)

	# dynamic challenge properties
	initial = db.Column(db.Integer, default=0)
	minimum = db.Column(db.Integer, default=0)
	decay = db.Column(db.Integer, default=0)

	def __init__(self, *args, **kwargs):
		super().__init__(**kwargs)
		self.value = kwargs.get('initial', 0)

class ContainerInfoModel(db.Model):
	__tablename__ = 'container_info'
	__mapper_args__ = {'polymorphic_identity': 'container_info'}
	container_id = db.Column(db.String(512), primary_key=True)
	challenge_id = db.Column(
		db.Integer,
		db.ForeignKey('challenges.id', ondelete='CASCADE')
	)
	team_id = db.Column(
		db.Integer,
		db.ForeignKey('teams.id', ondelete='CASCADE'),
		nullable=True
	)
	user_id = db.Column(
		db.Integer,
		db.ForeignKey('users.id', ondelete='CASCADE'),
		nullable=True
	)
	port = db.Column(db.Integer)
	ssh_username = db.Column(db.Text, nullable=True)
	ssh_password = db.Column(db.Text, nullable=True)
	timestamp = db.Column(db.Integer)
	expires = db.Column(db.Integer)
	team = relationship('Teams', foreign_keys=[team_id])
	user = relationship('Users', foreign_keys=[user_id])
	challenge = relationship(ContainerChallengeModel, foreign_keys=[challenge_id])

class ContainerSettingsModel(db.Model):
	__tablename__ = 'container_settings'
	__mapper_args__ = {'polymorphic_identity': 'container_settings'}
	key = db.Column(db.String(512), primary_key=True)
	value = db.Column(db.Text)
