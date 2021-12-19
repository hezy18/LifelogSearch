from flask import *
from flask_wtf import FlaskForm #基类
import whoosh
import whoosh.index as index
from whoosh import scoring,analysis,sorting
from whoosh.qparser import QueryParser
from whoosh.query import *
import numpy as np
import json
import calendar
from flask import session
from collections import OrderedDict
import datetime

timeline_app = Blueprint("timeline",__name__,url_prefix="/timeline/")

def search(date_start,date_end):
    timeline_ix = index.open_dir("./blueprints/timeline_index_dir")
    t_searcher = timeline_ix.searcher()
    daily_ix = index.open_dir("./blueprints/daily_index_dir")
    d_searcher = daily_ix.searcher()
    Result = OrderedDict()
    myquery = DateRange("date",date_start,date_end)
    dates = sorting.FieldFacet("date")
    s_times = sorting.FieldFacet('start_time')
    t_r = t_searcher.search(myquery,limit=2000,sortedby=[dates,s_times])
    for docnum, score in t_r.items():
        Info = t_searcher.stored_fields(docnum)
        date = str(Info['date'])[:10]
        if date not in Result:
            Result[date] = {'timeline':[],'daily_data':{}}
        Info['key_image_list'] = [ 'uu'.join(x.split('/')[1:]) for x in Info['key_image_list'].split(';')]
        Info['key_image_list'] = ';'.join(Info['key_image_list'])
        Info['tags'] = ','.join( Info['tags'].split(',')[:3]+['...'] ) if len(Info['tags'].split(','))>3 else Info['tags']
        Result[date]['timeline'].append('#'.join([str(Info['start_time'])[11:16],str(Info['end_time'])[11:16],
                                        Info['location'],Info['key_image_list'],Info['tags']]))
    d_r = d_searcher.search(myquery,limit=2000,sortedby=[dates])
    Dis_dict={'heart':'Average heart rate','calories':'Total calorie intake','steps':'Total steps'}
    for docnum, score in d_r.items():
        Info = d_searcher.stored_fields(docnum)
        date = str(Info['date'])[:10]
        for key in Info:
            if key != 'date' and Info[key]>0 and date in Result:
                Result[date]['daily_data'][Dis_dict[key]] = Info[key]
     
    return Result


@timeline_app.route('/search',methods=['GET','POST'])
def timeline_search():
    if request.method == 'POST' and request.form.get('search') :
        # search
        start_time = request.form.get('start_date')
        end_time = request.form.get('end_date')
        if start_time and end_time:
            start_time = datetime.datetime.strptime(start_time,"%Y-%m-%d")
            end_time = datetime.datetime.strptime(end_time,"%Y-%m-%d")
            result = search(start_time,end_time)
        else:
            result = search(datetime.datetime(2015,1,1),datetime.datetime(2018,12,31))
        print(result)
        return render_template('TimelinePage.html',content=result)
    else:
        result = search(datetime.datetime(2015,1,1),datetime.datetime(2015,12,31))
        return render_template('TimelinePage.html',content=result)


@timeline_app.route('/result/<img_list>',methods=['GET'])
def result_display(img_list):
    img_list = img_list.replace('uu','/')
    return render_template('TimelineResultPage.html',content=img_list)