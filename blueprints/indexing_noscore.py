from whoosh.fields import Schema, ID, TEXT, KEYWORD, STORED, NUMERIC, BOOLEAN, DATETIME
from whoosh import index,analysis
import os
from decimal import Decimal
import re
import json
import datetime


def Get_time(Time_str):
    try:
        return datetime.datetime(int(Time_str[:4]), int(Time_str[4:6]), int(Time_str[6:8]), 
                                int(Time_str[9:11]) ,int(Time_str[11:13]))
    except:
        try:
            Time_str = Time_str.strip().split('_')
            Date = Time_str[-2]
            Time = Time_str[-1][:6]
            return datetime.datetime(int(Date[:4]),int(Date[4:6]),int(Date[6:8]),int(Time[:2]),int(Time[2:4]))
        except:
            print(Time_str)
            return datetime.datetime.strptime('2014-12-31 00:00:00',"%Y-%m-%d %H:%M:%S")

# create a schema
my_ana = analysis.KeywordAnalyzer(commas=True,lowercase=True) | analysis.LowercaseFilter() | analysis.StopFilter()

shot_schema = Schema(shot_id=ID(unique=True),
#first level
color1=TEXT(stored=True,analyzer=my_ana),color2=TEXT(stored=True,analyzer=my_ana),color3=TEXT(stored=True,analyzer=my_ana),color4=TEXT(stored=True,analyzer=my_ana),color5=TEXT(stored=True,analyzer=my_ana),color6=TEXT(stored=True,analyzer=my_ana),
color7=TEXT(stored=True,analyzer=my_ana),color8=TEXT(stored=True,analyzer=my_ana),color9=TEXT(stored=True,analyzer=my_ana),brightness=NUMERIC(float,stored=True),contrast=NUMERIC(float,stored=True),saturation=NUMERIC(float,stored=True),
#second level
year=NUMERIC(int,stored=True), month=NUMERIC(int,stored=True), day=NUMERIC(int,stored=True), weekday=KEYWORD(commas=True,scorable=True), hour_start=NUMERIC(int,stored=True), hour_end=NUMERIC(int,stored=True),date=DATETIME, 
loc_year=NUMERIC(int,stored=True), loc_month=NUMERIC(int,stored=True), loc_day=NUMERIC(int,stored=True), loc_weekday=KEYWORD(commas=True,scorable=True), loc_hour_start=NUMERIC(int,stored=True), loc_hour_end=NUMERIC(int,stored=True),loc_date=DATETIME, 
tags=TEXT(stored=True, analyzer=my_ana, phrase=True), 
past_tags=TEXT(stored=True, analyzer=my_ana, phrase=True), 
future_tags=TEXT(stored=True, analyzer=my_ana, phrase=True),
elevation=NUMERIC(int,stored=True),speed=NUMERIC(float,stored=True),calories=NUMERIC(int,decimal_places=2,stored=True),heart=NUMERIC(int,stored=True),  steps=NUMERIC(int,stored=True), distance=NUMERIC(float,stored=True),#gsr=NUMERIC(float,stored=True))
#third level
location=KEYWORD(commas=True,scorable=True,analyzer=my_ana),activity=TEXT(stored=True,analyzer=my_ana),companion=KEYWORD(commas=True),
is_moving=BOOLEAN(stored=True),
past_location=KEYWORD(commas=True,analyzer=my_ana,scorable=True),past_activity=TEXT(stored=True,analyzer=my_ana),past_companion=KEYWORD(commas=True),
past_is_moving=BOOLEAN(stored=True),
future_location=KEYWORD(commas=True,analyzer=my_ana,scorable=True),future_activity=TEXT(stored=True,analyzer=my_ana),future_companion=KEYWORD(commas=True),
future_is_moving=BOOLEAN(stored=True),
)

# create index
if not os.path.exists("index_noscore_dir"):
    os.mkdir("index_noscore_dir")

shot_ix = index.create_in("index_noscore_dir", shot_schema)

writer = shot_ix.writer()

print('location expand loading')
loc_expand_file = open('../../LSC2020_dataset/process_exblur/Expand_location.txt','r')
loc_expand_dict = {}
for line in loc_expand_file:
    line = line.strip().split(':')
    if len(line[1])==0:
        continue
    words = line[1].strip().split(',')
    loc_expand_dict[line[0]] = words
loc_expand_file.close()

print('basic data loading')
basic_file = open('../../LSC2020_dataset/process_exblur/basic_info.txt','r')
basic_dict = {}
for line in basic_file:
    line = line.strip().split('\t')
    img_name = line[0].split('/')[-1]
    basic_dict[img_name] = {}
    basic_dict[img_name]['color'] = line[1].split(',')
    b = [ float(x) for x in line[2].split(',')]
    basic_dict[img_name]['brightness'] = b[0]
    basic_dict[img_name]['contrast'] = b[1]
    basic_dict[img_name]['saturation'] = b[2]
basic_file.close()

print('tag data loading')
tags_file=open('../../LSC2020_dataset/process_exblur/all_tags_timeupdate_feb17.txt','r')
tags_dict = {}
img_utc_time = {}
for line in tags_file:
    line = line.strip().split('\t')
    img_name = line[0].strip()
    img_utc_time[img_name] = datetime.datetime.strptime(line[1],"UTC_%Y-%m-%d_%H:%M") if line[1]!='unknown' else Get_time(img_name)
    tags_dict[img_name] = {}
    for key in line[2:]:
        key = key.strip().split('##')
        if key[0] not in tags_dict[img_name]:
            tags_dict[img_name][key[0]]=[]
        tags_dict[img_name][key[0]].append((key[2],key[3],key[1])) # position,description, score

print('lifelog data loading')
lifelog_file=open('../../LSC2020_dataset/process_exblur/all_lifelog.txt','r')
line1 = lifelog_file.readline().strip().split('\t')
lifelog_title = {}
lifelog_titler = {}
lifelog_dict = {}
for i,k in enumerate(line1):
    lifelog_title[k] = i
    lifelog_titler[i] = k
for line in lifelog_file:
    line = line.strip().split('\t')
    utc_time = datetime.datetime.strptime(line[0],"%Y-%m-%d %H:%M:%S")
    lifelog_dict[utc_time] = {}
    for i,data in enumerate(line[1:]):
        if lifelog_titler[i+1] == 'loc_time':
            data = datetime.datetime.strptime(line[0],"%Y-%m-%d %H:%M:%S")
        lifelog_dict[utc_time][lifelog_titler[i+1]] = data

# transform utc time and local time
loc2utc = {}
for utc_time in lifelog_dict:
    loc_time = lifelog_dict[utc_time]['loc_time']
    loc2utc[loc_time] = utc_time

print('Get shot tags')
shot_tags={} # to be saved
shot_stime = {}
shot_etime = {}
Shot_basic = {}
shot_file = open('../../LSC2020_dataset/process_exblur/Shotmrg_newkey.txt','r')
for line in shot_file:
    if not line:
        break
    shot_info=line.strip().split("\t")
    try:
        shot_id=int(shot_info[0])
    except:
        print(shot_info)
        continue
    img_list = shot_info[2].strip().split(';')
    start_time = datetime.datetime.strptime('2019-01-01 00:00:00',"%Y-%m-%d %H:%M:%S") 
    end_time = datetime.datetime.strptime('2014-12-31 00:00:00',"%Y-%m-%d %H:%M:%S")
    key_img = shot_info[-1].split('/')[-1]
    Shot_basic[shot_id] = basic_dict[key_img]
    shot_tags[shot_id] = {}
    for img in img_list:
        img = img.strip().split('/')[-1]
        if img in img_utc_time:
            start_time = min(start_time, img_utc_time[img])
            end_time = max(end_time,img_utc_time[img])
        else:
            start_time = min(start_time, Get_time(img))
            end_time = max(end_time,Get_time(img))
        if img not in tags_dict:
            print(img)
            continue
        for t in tags_dict[img]:
            for info in tags_dict[img][t]:
                dis = ''
                if info[1] != 'NULL':
                    dis = ' and '.join(info[1].split(','))+' '
                    if t not in shot_tags[shot_id]:
                        shot_tags[shot_id][t] = 0
                    shot_tags[shot_id][t] = max(shot_tags[shot_id][t],float(info[2]))
                dis += t
                if info[0] != 'NULL':
                    if info[1] == 'NULL':
                        if t not in shot_tags[shot_id]:
                            shot_tags[shot_id][t] = 0
                            shot_tags[shot_id][t] = max(shot_tags[shot_id][t],float(info[2]))
                    else:
                        if dis not in shot_tags[shot_id]:
                            shot_tags[shot_id][dis] = 0
                        shot_tags[shot_id][dis] = max(shot_tags[shot_id][dis],float(info[2]))
                        t0 = t+ ' at '+' and '.join(info[0].split(','))
                        t0 = t0.replace("up","top").replace("down","bottom").replace("mid","middle")
                        if t0 not in shot_tags[shot_id]:
                            shot_tags[shot_id][t0] = 0
                            shot_tags[shot_id][t0] = max(shot_tags[shot_id][t0],float(info[2]))
                    dis += ' at '+' and '.join(info[0].split(','))
                    dis = dis.replace("up","top").replace("down","bottom").replace("mid","middle")
                if dis in shot_tags[shot_id]:
                    shot_tags[shot_id][dis] = max(shot_tags[shot_id][dis],float(info[2]))
                else:
                    shot_tags[shot_id][dis] = float(info[2])
            #print(t,tags_dict[img][t])
    shot_stime[shot_id],shot_etime[shot_id] = [start_time,end_time]
    
shot_file.close()

import nltk
def All_noun(Sentence):
    if len(Sentence)==0:
        return ''
    tokens = nltk.sent_tokenize(Sentence)
    word_list = nltk.pos_tag(nltk.word_tokenize(tokens[0]))
    Nouns = []
    for word in word_list:
        if word[1] in ['NN','NNS','NNP']:
            Nouns.append(word[0])
    return ','.join(Nouns)

past_shot_tags = {} # to be saved
future_shot_tags = {}    
shot_file.close()
shot_file = open('../../LSC2020_dataset/process_exblur/Shotmrg_newkey.txt','r')
Outfile = open('../../LSC2020_dataset/process_exblur/Shotinfo_search_noscore.txt','w')
cnt = 0
for line in shot_file:
    cnt += 1
    if not line:
        break
    shot_info=line.strip().split("\t")
    try:
        shot_id=int(shot_info[0])
    except:
        print(shot_info)
        continue
    if cnt%200==0:
        print('dealing with shot:',shot_id)
    img_list = shot_info[2].strip().split(';')
    '''
    start_time = datetime.datetime.strptime(shot_info[3],"%Y-%m-%d %H:%M:%S") 
    end_time = datetime.datetime.strptime(shot_info[4],"%Y-%m-%d %H:%M:%S")
    '''
    start_time = shot_stime[shot_id]
    end_time = shot_etime[shot_id]
    img_key = shot_info[5].strip()

    this_tags = []
    for t,s in shot_tags[shot_id].items():
        this_tags += [t]
    this_tags = ','.join(this_tags)
    future_shot_tags[shot_id]={}
    past_shot_tags[shot_id]={}
    for p_shot in shot_tags:
        if p_shot<shot_id and shot_etime[p_shot] <= start_time and shot_etime[p_shot] > start_time-datetime.timedelta(minutes=60):
            for t in shot_tags[p_shot]:
                if t not in past_shot_tags[shot_id]:
                    past_shot_tags[shot_id][t]= 0
                past_shot_tags[shot_id][t] = max(past_shot_tags[shot_id][t],shot_tags[p_shot][t])
        elif p_shot>shot_id and shot_stime[p_shot] >= end_time and shot_stime[p_shot] < end_time + datetime.timedelta(minutes=60):
            for t in shot_tags[p_shot]:
                if t not in future_shot_tags[shot_id]:
                    future_shot_tags[shot_id][t] = 0
                future_shot_tags[shot_id][t] = max(future_shot_tags[shot_id][t] , shot_tags[p_shot][t])
    this_past_t = []
    for t,s in past_shot_tags[shot_id].items():
        this_past_t += [t]
    this_past_t = ','.join(this_past_t)
    this_future_t = []
    for t,s in future_shot_tags[shot_id].items():
        this_future_t += [t]
    this_future_t = ','.join(this_future_t)

    this_lifelog = {}
    past_lifelog = {}
    future_lifelog = {}
    for k in ['location','activity']:
        this_lifelog[k],past_lifelog[k],future_lifelog[k]=[set(),set(),set()]
    for k in ['elevation','speed','calories','heart','steps','distance']:
        this_lifelog[k]=[]
    m = 'is_moving'
    this_lifelog[m],past_lifelog[m],future_lifelog[m] = [False,False,False]

    n_start_time = start_time
    start_time  -= datetime.timedelta(seconds=start_time.second)
    n_end_time = end_time
    end_time -= datetime.timedelta(seconds=end_time.second)
    loc_stime = lifelog_dict[start_time]['loc_time']
    loc_etime = lifelog_dict[end_time]['loc_time']
    m_time = start_time - datetime.timedelta(seconds=60)
    while m_time <= end_time:
        m_time += datetime.timedelta(seconds=60)
        m_info = lifelog_dict[m_time]
        this_lifelog['location'] |= set(re.split(r'[/,]',m_info['location'].strip()))
        this_lifelog['activity'].add(m_info['activity'])
        if m_info['is_moving']=='True':
            this_lifelog['is_moving'] = True
        for k in ['elevation','speed','calories','heart','steps',]:#'distance']:
            if m_info[k] == 'NULL':
                continue
            this_lifelog[k].append(float(m_info[k]) if '.' in m_info[k] else int(m_info[k]))
    if len(this_lifelog['location'])==0:
        this_lifelog['location'] = ['NULL']
    loc_set = set()
    for loc in this_lifelog['location']:
        if loc in loc_expand_dict:
            loc_set |= set(loc_expand_dict[loc])
    this_lifelog['location'] |= loc_set
    if len(this_lifelog['activity'])==0:
        this_lifelog['activity'] = ['NULL']
    this_lifelog['location'] = ",".join(list(this_lifelog['location']))
    this_lifelog['location'] = this_lifelog['location'].lower().replace('the ','').replace(' the ','')
    this_lifelog['activity'] = ",".join(list(this_lifelog['activity']))
    for k in ['elevation','calories','steps',]:#'distance']:
        if len(this_lifelog[k]):
            this_lifelog[k] = sum(this_lifelog[k])
        else:
            this_lifelog[k] = -1
    for k in ['speed','heart']:
        if len(this_lifelog[k]):
            this_lifelog[k] = sum(this_lifelog[k]) / len(this_lifelog[k])
        else:
            this_lifelog[k] = -1
    
    m_time = start_time-datetime.timedelta(minutes=61)
    while m_time <start_time:
        m_time += datetime.timedelta(minutes=1)
        try:
            m_info = lifelog_dict[m_time]
        except:
            continue
        if m_info['is_moving']=='True':
            past_lifelog['is_moving'] = True
        past_lifelog['location'] |= set(re.split(r'[/,]',m_info['location'].strip()))
        past_lifelog['activity'].add((m_info['activity'] ))
    if len(past_lifelog['location'])==0:
        past_lifelog['location'] = ['NULL']
    loc_set = set()
    for loc in past_lifelog['location']:
        if loc in loc_expand_dict:
            loc_set |= set(loc_expand_dict[loc])
    past_lifelog['location'] |= loc_set
    if len(past_lifelog['activity'])==0:
        past_lifelog['activity'] = ['NULL']
    past_lifelog['location'] = ",".join(list(past_lifelog['location']))
    past_lifelog['location'] = past_lifelog['location'].lower().replace('the ','').replace(' the ','')
    past_lifelog['activity'] = ",".join(list(past_lifelog['activity']))
    
    m_time = end_time-datetime.timedelta(seconds=end_time.second)
    while m_time < end_time+datetime.timedelta(minutes=60):
        m_time += datetime.timedelta(minutes=1)
        try:
            m_info = lifelog_dict[m_time]
        except:
            continue
        if m_info['is_moving']=='True':
            future_lifelog['is_moving'] = True 
        future_lifelog['location'] |= set(re.split(r'[/,]',m_info['location'].strip()))
        future_lifelog['activity'].add(m_info['activity'] )
    if len(future_lifelog['location'])==0:
        future_lifelog['location'] = ['NULL']
    loc_set = set()
    for loc in future_lifelog['location']:
        if loc in loc_expand_dict:
            loc_set |= set(loc_expand_dict[loc])
    future_lifelog['location'] |= loc_set
    if len(future_lifelog['activity'])==0:
        future_lifelog['activity'] = ['NULL']
    future_lifelog['location'] = ",".join(list(future_lifelog['location']))
    future_lifelog['location'] = future_lifelog['location'].lower().replace('the ','').replace(' the ','')
    future_lifelog['activity'] = ",".join(list(future_lifelog['activity']))
    
    start_time = n_start_time
    end_time = n_end_time
    Output_line = [str(shot_id),
                   str(start_time.year),str(start_time.month),str(start_time.day),str(start_time.strftime("%A")),
                   str(start_time.hour),str(end_time.hour),
                   str(loc_stime.year), str(loc_stime.month),str(loc_stime.day),str(loc_stime.strftime("%A")),
                   str(loc_stime.hour), str(loc_etime.hour),
                   this_tags, this_lifelog['location'],this_lifelog['activity'], str(this_lifelog['is_moving']),
                   str(this_lifelog['elevation']), str(this_lifelog['speed']), str(this_lifelog['calories']), str(this_lifelog['heart']), str(this_lifelog['steps']), #distance = this_lifelog['distance'],
                   this_past_t, past_lifelog['location'], past_lifelog['activity'],
                   this_future_t, future_lifelog['location'], future_lifelog['activity']]
    
    Outfile.write("\t".join(Output_line)+'\n')
        
    writer.add_document( shot_id=str(shot_id), 
    #first level
    color1=Shot_basic[shot_id]['color'][0],color2=Shot_basic[shot_id]['color'][1],color3=Shot_basic[shot_id]['color'][2],color4=Shot_basic[shot_id]['color'][3],color5=Shot_basic[shot_id]['color'][4],color6=Shot_basic[shot_id]['color'][5],
    color7=Shot_basic[shot_id]['color'][6],color8=Shot_basic[shot_id]['color'][7],color9=Shot_basic[shot_id]['color'][8],brightness=Shot_basic[shot_id]['brightness'],contrast=Shot_basic[shot_id]['contrast'],saturation=Shot_basic[shot_id]['saturation'],
    #second level
    year=int(start_time.year),month=int(start_time.month),day=int(start_time.day),weekday=start_time.strftime("%A"),
    hour_start=int(start_time.hour),hour_end=int(end_time.hour),
    loc_year= int(loc_stime.year), loc_month=int(loc_stime.month),loc_day=int(loc_stime.day),loc_weekday=loc_stime.strftime("%A"),
    loc_hour_start =int(loc_stime.hour), loc_hour_end = int(loc_etime.hour),
    tags = this_tags, past_tags = this_past_t, future_tags = this_future_t, 
    elevation = this_lifelog['elevation'], speed = this_lifelog['speed'], calories = this_lifelog['calories'], heart = this_lifelog['heart'], steps = this_lifelog['steps'], #distance = this_lifelog['distance'],
    #third level
    location = this_lifelog['location'],
    activity = this_lifelog['activity'], is_moving = this_lifelog['is_moving'],
    past_location = past_lifelog['location'],
    past_activity = past_lifelog['activity'],past_is_moving = past_lifelog['is_moving'],
    future_location = future_lifelog['location'], 
    future_activity = future_lifelog['activity'],future_is_moving=future_lifelog['is_moving']
    ) 

writer.commit()

tags_file.close()
lifelog_file.close()
shot_file.close()
Outfile.close()

print('convert tags')
for tags_dict in [shot_tags,future_shot_tags,past_shot_tags]:
    for shot in tags_dict:
        for t in tags_dict[shot]:
            tags_dict[shot][t] = str(tags_dict[shot][t])
print('save json file')
tags_all = {'shot_tags':shot_tags,'future_tags':future_shot_tags,'past_tags':past_shot_tags}
with open('tags_data.json','w') as J_file:
    json.dump(tags_all,J_file)

print('all done!')