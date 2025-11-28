
import os
BASE_DIR=os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY="dev"
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(BASE_DIR,'pascom.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS=False
    ADMIN_PASSWORD="trindade123"
