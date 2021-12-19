from flask import Blueprint
from flask import Flask,redirect,url_for,g
from blueprints import searchclass

from blueprints.HomePage import home
from blueprints.SearchPage import search_app as search#home as search
from blueprints.ResultPage import home as result
from blueprints.ViewPage import home as view
from blueprints.ImagePage import img_app as img_search
from blueprints.TimelinePage import timeline_app as timeline
from blueprints.DenoisePage import denoise_app as denoise

DEBUG = True 

app = Flask(__name__)

app.register_blueprint(home)
app.register_blueprint(search)
app.register_blueprint(result)
app.register_blueprint(view)
app.register_blueprint(img_search)
app.register_blueprint(timeline)
app.register_blueprint(denoise)
app.secret_key = 'LSC2020' 

app.config.from_object(__name__)

# @app.before_request
# def before_request():
#     g.searcher = searchclass.SearchClass()

# @app.teardown_request
# def teardown_request(exception):
#     g.searcher.__close__()

@app.route('/')
def go_to_home():
    return redirect(url_for('home.home_page'))

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5000,debug=True)
