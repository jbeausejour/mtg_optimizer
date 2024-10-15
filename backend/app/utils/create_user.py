from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.user import User


def create_user():
    # Create a new user
    username = "Julz"
    email = "jules.beausejour@gmail.com"
    password = "Julz"  # Replace with the actual password

    # Create the user object
    new_user = User(username=username, email=email)
    new_user.set_password(password)

    # Add the user to the database
    db.session.add(new_user)
    db.session.commit()

    print(f"User '{username}' created successfully.")
    