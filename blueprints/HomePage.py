from flask import *
from flask_wtf import FlaskForm #基类
from wtforms import BooleanField,TextAreaField,StringField,PasswordField,RadioField,SelectField, IntegerField,SubmitField

'''
用flash给模板传递消息，需要对内容加密，设置secret_key，做加密消息的混淆
模板中需要遍历消息
'''

home = Blueprint("home",__name__,url_prefix="/home")
#app = Flask(__name__)
#app.secret_key = 'LSC2020' #自行设置字符串

@home.route('/')
def home_page():
    session.clear()
    return render_template('HomePage.html')
    #return redirect(url_for('get_request'))