from main import db

class User(db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.string(100), nullable=False)

    email = db.Column(db.string(255), unique=True, nullable=False)

    password_hash = db.Column(db.Text, nullable=False)