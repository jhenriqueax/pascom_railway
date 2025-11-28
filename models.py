
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

class Month(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(80),nullable=False)
    year=db.Column(db.Integer)
    month_number=db.Column(db.Integer)
    masses=db.relationship("Mass",backref="month",lazy=True)

class Mass(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    date=db.Column(db.String(10),nullable=False)
    time=db.Column(db.String(5),nullable=False)
    description=db.Column(db.String(180))
    month_id=db.Column(db.Integer,db.ForeignKey("month.id"))
    availabilities=db.relationship("Availability",backref="mass",lazy=True)

class Person(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(120),nullable=False)

class Availability(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    person_id=db.Column(db.Integer,db.ForeignKey("person.id"))
    mass_id=db.Column(db.Integer,db.ForeignKey("mass.id"))
    role=db.Column(db.String(40))
