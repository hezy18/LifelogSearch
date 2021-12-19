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

def search(date_start,date_end):
    timeline_ix = index.open_dir("timeline_index_dir")
    t_searcher = timeline_ix.searcher()
    daily_ix = index.open_dir("daily_index_dir")
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


result = search(datetime.datetime(2015,1,1),datetime.datetime(2018,12,31))
cnt = []
for date in result:
    print(date)
    print(len(result[date]['timeline']))
    cnt.append(len(result[date]['timeline']))
print(sum(cnt))
print(min(cnt))
print(max(cnt))
