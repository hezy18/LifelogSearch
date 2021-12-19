from flask import *
from flask_wtf import FlaskForm #基类
from whoosh import analysis,scoring
import whoosh.index as whoosh_index
from . import searchclass#,auto_input
from . import util
import nltk
import numpy as np
import cv2
import json
import calendar
import time
from flask import session,g

search_app = Blueprint("search",__name__,url_prefix="/search/")

@search_app.route('/',methods=['GET','POST'])
def search_page():
    limit_num=20
    mySearch = searchclass.SearchClass(weighting_type='MW_tag')
    s_time = time.time()
    if request.method == 'POST' and request.form.get('form_fill') :
        # click the button "Fill in forms"
        real_tags = {}
        text = request.form.get('text_input') # get text from the text box
        #if text:
        if True:
            # [parsed_query,real_tags] = g.searcher.QueryParser(text,'info_dictionary_mar8.json')
            [parsed_query,real_tags] = mySearch.QueryParser(text,'info_dictionary_mar8.json')  # parse query into dict
            if 'query_term' in session:
                # if this is not the first time to fill the forms, update the query. [for multi-round search (mainly used in result page)]
                # util.merge(session['query_term'],parsed_query,session['parsed_query'])
                session['this_parsed_query'] = parsed_query
                #print(session["query_term"],parsed_query,session["all_parsed_query"])
                query_term = util.merge(session['query_term'],parsed_query,session['all_parsed_query']) # add, update, and delete keywords
            else:
                # first-time query
                # session['query_term'] = parsed_query
                session['this_parsed_query'] = parsed_query
                query_term = parsed_query
                session['all_parsed_query'] = {}
            # session['query_term']['text'] = text
            query_term['text'] = text
            # session['parsed_query'] = parsed_query
            session['real_tags'] = real_tags
            # session['js_query_term'] = util.js_query(session['query_term'])
            session['js_query_term'] = util.js_query(query_term)
        mySearch.__close__()
        print('query parse time: %f s'%(round(time.time()-s_time,2)))
        return render_template('SearchPage.html',formcontent=session['js_query_term'])
    elif request.method == 'POST' and request.form.get('search') :
        print(dict(request.form))
        this_query = util.get_query_term(dict(request.form),rank_list_len=limit_num)[0]
        # session['query_term']['text'] = request.form.get('text_input')
        
        for key in this_query:
            if 'location' in key and type(this_query[key]) != dict:
                this_query[key] = list(set(this_query[key]))
        session['all_parsed_query'] = util.merge(session['all_parsed_query'],session['this_parsed_query'],session['all_parsed_query'])
        # [img_key_list, img_all_list,shot_id_dict,session['extra_info']] = g.searcher.QueryMain(util.add_tags(this_query,session['real_tags']))
        # QUERY FOR IMAGES
        [img_key_list, img_all_list,shot_id_dict,session['extra_info']] = mySearch.QueryMain(util.add_tags(this_query,session['real_tags']),limit_num=limit_num)
        mySearch.__close__()

        # for key in this_query:
        #     session['query_term'][key] = this_query[key]
        session['query_term'] = this_query
        session['query_term']['text'] = request.form.get('text_input')
        session['result_key'] = img_key_list
        session['result_all'] = img_all_list
        if 'shot_id' not in session:
            session['shot_id'] = {}
        session['shot_id'] = dict( shot_id_dict, **session['shot_id'])
        print('search time: %f s'%(round(time.time()-s_time,2)))
        return redirect(url_for('search_result.display_result'))
    else:
        # refresh the page
        session.clear()
        mySearch.__close__()
        return render_template('SearchPage.html',formcontent={'elevation_range':'above'})