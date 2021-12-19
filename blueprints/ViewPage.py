from flask import *
from flask_wtf import FlaskForm #基类
from wtforms import BooleanField,TextAreaField,StringField,PasswordField,RadioField,SelectField, IntegerField,SubmitField
from . import search

home = Blueprint("viewimage",__name__,url_prefix="/viewimage")


@home.route('/',methods=['GET','POST'])
def viewimage():
    Imgs = []
    with open("img_list.txt",'r') as File:
        for line in File:
            Imgs.append(File)
