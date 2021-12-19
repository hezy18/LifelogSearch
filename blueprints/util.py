import cv2
import numpy as np
import calendar
import copy
import re

def get_color(color):
    if color == '#c0c0c0':
        return 'NULL'
    color = color[1:]
    RGB=[]
    for i in range(3):
        RGB.append(int('0x'+color[i*2:i*2+2],16))
        # print('color:',color)
        # RGB.append(int(color[i*2:i*2+2],16))
    BGR = np.array([[[RGB[2],RGB[1],RGB[0]]]]).astype(np.uint8)
    hsv = cv2.cvtColor(BGR,cv2.COLOR_BGR2HSV)
    range_min=np.array([[0,0,0],[0,0,47],[0,0,151],[0,43,46],[156,43,46],[11,43,46],
                        [26,43,46],[35,43,46],[78,43,46],[100,43,46],[125,43,46]])
    range_max=np.array([[180,255,46],[180,43,150],[180,30,255],[10,255,255],[180,255,255],[25,255,255],
                       [34,255,255],[77,255,255],[99,255,255],[124,255,255],[155,255,255]])
    range_name = ['black','gray','white','red','red','orange','yellow','green','cyan','blue','purple']
    for color_idx in range(len(range_name)):
        if cv2.inRange(hsv,range_min[color_idx],range_max[color_idx]):
            return range_name[color_idx]

def color2str(color):
    color_dict = {'black':'#000000','gray':'#808080','white':'#ffffff','red':'#ff0000','orange':'#ff8000','yellow':'#ffff00','green':'#00ff00','cyan':'#00ffff','blue':'#0000ff','purple':'#ff00ff'}
    return color_dict[color] if color in color_dict else '#c0c0c0'

def js_query(query_term,img_feedback_str="", tag_feedback_str=""):
    Out_query_term = {}
    Date = []
    Tags = {}
    if len(img_feedback_str):
        Out_query_term['img_feedback'] = img_feedback_str
    if len(tag_feedback_str):
        Out_query_term['Tag_feedback'] = tag_feedback_str
    if 'loc_year' in query_term:
        Date += [str(x) for x in query_term['loc_year']]
    if 'loc_month' in query_term:
        Date += [calendar.month_name[x] for x in query_term['loc_month']]
    if len(Date):
        Out_query_term['loc_date'] = ','.join(Date)
    if 'loc_weekday' in query_term:
        Out_query_term['loc_weekday'] = ','.join(query_term['loc_weekday'])
    for key in query_term:
        if 'tag' in key and key !='tag_feedback' and key != 'tag_feedback_str':
            Out_query_term[key[:-1]] = query_term[key]
        elif 'location' in key or 'activity' in key or 'loc_time' in key:
            Out_query_term[key] = ','.join(query_term[key])
    for key in query_term:
        if query_term[key] == "none":
            continue
        if 'color' in key:
            Out_query_term[key] = color2str(query_term[key][0])
        elif key in ['brightness','contrast','saturation']:
            Out_query_term[key] = query_term[key]
    if 'text' in query_term:
        Out_query_term['text'] = query_term['text']
    return Out_query_term

def merge_q(query_term, session_dict):
    for key in session_dict:
        print(key,session_dict[key])
    t_query_term = query_term
    Tags = session_dict['real_tags']
    for key in session_dict['add_query_term']:
        if key not in query_term:
            t_query_term[key] = session_dict['add_query_term'][key]
        elif type(query_term[key]) in [list,set]:
            t_query_term[key] = list(set(query_term[key]) | set(session_dict['add_query_term'][key]))
        else:
            t_query_term[key] = session_dict['add_query_term'][key]
    for key in session_dict['delete_query_term']:
        if key not in query_term:
            continue
        if 'tag' in key:
            delete_list = []
            for k in session_dict['delete_query_term'][key]:
                for k2 in Tags[key]:
                    if k in Tags[key][k2]:
                        delete_list.append(k2)
            for k in delete_list:
                Tags[key].pop(k)
        if type(query_term[key]) in [list,set]:
            t_query_term[key] = list(set(query_term[key]) - set(session_dict['delete_query_term'][key]))
        else:
            t_query_term.pop(key)
    for key in session_dict['alter_query_term']:
        t_query_term[key] = session_dict['alter_query_term'][key]
    print(t_query_term)
    return t_query_term,Tags

def merge(query_term, new_query, old_query):
    for key in new_query:
        # if key not in query_term:
        #     query_term[key] = []
        # for t in new_query[key]:
        #     if t not in query_term[key]:
        #         query_term[key].append(t)
        if key not in query_term:
            query_term[key] = []
        if key not in old_query:
            query_term[key] += new_query[key]
        else:
            for t in new_query[key]:
                if t not in old_query[key] and t not in query_term[key]:
                    query_term[key].append(t)
    # for key in old_query:
        # if key not in new_query and key not in query_term:

    return query_term

def add_tags(query_term, real_tags):
    new_query_term = copy.deepcopy(query_term)
    for key in query_term:
        if '_tags' not in key:
            continue
        add_tags = []
        for t in query_term[key]:
            if t in real_tags[key]:
                add_tags += real_tags[key][t]
        new_query_term[key] = list(set(query_term[key]+add_tags))
    return new_query_term

def get_query_term(form,session={},rank_list_len=10):
    query_term = {'loc_year':[],'loc_day':[],'loc_month':[],'utc_year':[],'utc_day':[],'utc_month':[]}
    # basic information
    ## color
    for i in range(1,10):
        colori = 'color'+str(i)
        if colori not in form:
            continue
        color = get_color(form[colori])
        if color == 'NULL':
            continue
        query_term[colori]=[color]
        if color =='white':
            query_term[colori].append('gray')
    ## basic list
    for key in ['brightness','contrast','saturation']:
        if key in form:
            query_term[key] = form[key]
            # query_term[key] = form[key][0]
    # detail destription
    ## time
    for key in ['loc_date','utc_date']:
        typ = key.split('_')[0]
        if key not in form or len(form[key])==0:
        # if key not in form or len(form[key][0])==0:
            continue
        t = form[key][0].split(',')
        for time_p in t:
            if time_p in ['2015','2016','2017','2018']:
                query_term[typ+'_year'].append(time_p)
            elif time_p.isdigit():
                query_term[typ+'_day'].append(int(time_p))
            else:
                try:
                    query_term[typ+'_month'].append(list(calendar.month_name).index(time_p))
                except:
                    query_term[typ+'_month'].append(list(calendar.month_abbr).index(time_p))
    for key in ['loc_weekday','loc_time','utc_weekday','utc_time']:
        if key not in form:
            continue
        t = form[key]
        # t = form[key][0]
        if t and t!='null':
            query_term[key] = t.split(',')
    for key in ['loc_timer','utc_timer']:
        if key not in form:
            continue
        t = form[key]
        # t = form[key][0]
        if t and t!='0,24':
            [ query_term[key.split('_')[0]+'_start_time'], query_term[key.split('_')[0]+'_end_time'] ] = form[key][0].split(',')
    ## tags
    for t in ['this','future','past']:
        all_tags = []
        for i in range(20):
            tag = t+'_tag'+str(i)
            # if tag in form and len(form[tag][0]):
            if tag in form and len(form[tag]):
                t_tag = form[tag][0]
                all_tags.append(t_tag)
        query_term[t+'_tags']= all_tags
    ## biometrics
    for key in ['elevation','calories','steps','speed','heart']:
        if key in form:
            query_term[key] = form[key]
            # query_term[key] = form[key][0]
            query_term[key+'_range'] = form[key+'_range']
            # query_term[key+'_range'] = form[key+'_range'][0]
            if not query_term[key+'_range']:
                query_term[key+'_range'] = 'above'
    
    # semantic description
    for key in ['this_location','this_activity','future_location', \
                'future_activity','past_location','past_activity']:
        if key not in form:
            continue
        # t = form[key][0]
        t = form[key]
        if t and 'activity' in key:
            if 'activity' in ['transport', 'airplane', 'running', 'walking']:
                m_key = key.split('_')[0]+'_is_moving' if key[0] != t else 'is_moving'
                query_term[m_key] = 'yes'
        if t:
            t = t.lower().replace('the ','').replace(' the ','')
            query_term[key] = t.split(',')
    
    # negative feedback
    img_feedback_list = []
    tags_feedback_str = ''
    if 'Tag_feedback' in form:
        # t = form['Tag_feedback'][0]
        t = form['Tag_feedback']
        query_term['tag_feedback'] = []
        for t_tag in re.split(',',t):
            if len(t_tag) and t_tag[0] == ' ':
                t_tag = t_tag[1:]
            query_term['tag_feedback'].append(t_tag)
        tags_feedback_str = t
    if 'img_feedback' in form: 
        query_term['img_feedback'] = {'img':[],'location':[],'time':[]}
        # t = form['img_feedback'][0]
        t = form['img_feedback']
        if len(t):
            img_feedback_list.append(t)               
        for line in t.split('\n'):
            line = line.split(' ')
            if len(line)<7 and len(line)>1:
                query_term['img_feedback']['img'].append(int(line[-1].strip()))
            elif len(line)>6:
                query_term['img_feedback'][line[-1].strip()].append(int(line[-3].strip()))
    # print("REsult")
    # if 'result_key' in session:
    #     print(session["result_key"])
    for k in range(rank_list_len):
        if 'img_feedback' not in query_term:
            query_term['img_feedback'] = {'img':[],'location':[],'time':[]}
        # print(k)
        if 'shot_id' in session:
            try:
                shotid = session['shot_id'][session['result_key'][k]]
            except:
                shotid = -1
        if 'img_checkbox'+str(k) in form:
            img_feedback_list.append('exclude shot '+str(shotid))#.split('.')[0])
            query_term['img_feedback']['img'].append(shotid)
        if 'semantic_checkbox'+str(k) in form:
            # img_feedback_list.append('exclude images taken at '+str(int(session['extra_info'][k]["loc_date"][-5:-3]))+"o'clock")
            img_feedback_list.append('exclude images similar to shot '+str(shotid)+' in time')
            query_term['img_feedback']['time'].append(shotid)
        if 'location_checkbox'+str(k) in form:
            # img_feedback_list.append('exclude images taken at '+session['extra_info'][k]["small_location"])
            img_feedback_list.append('exclude images similar to shot '+str(shotid)+' in location')
            query_term['img_feedback']['location'].append(shotid)

    # for k in range(rank_list_len):
    #     if 'semantic_checkbox'+str(k) not in form:
    #         continue
    #     try:
    #         t_s = form['semantic_select'+str(k)][0]
    #     except:
    #         continue
    #     if 'img_feedback' not in query_term:
    #         query_term['img_feedback'] = {'img':[],'location':[],'time':[]}
    #     img_feedback_list.append('exclude images similar to '+session['result_key'][k]+' in '+t_s)
    #     query_term['img_feedback'][t_s].append(session['shot_id'][session['result_key'][k]])

    pop_key =[]
    for key in query_term:
        if query_term[key] == [] or query_term[key] == '':
            pop_key.append(key)
    for key in pop_key:
        query_term.pop(key)
    return query_term,'\n'.join(sorted(list(set(img_feedback_list)),reverse=True)), tags_feedback_str
