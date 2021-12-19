from whoosh.fields import Schema, ID, TEXT, KEYWORD, STORED, NUMERIC, BOOLEAN, DATETIME
from whoosh import index,analysis
import os
from decimal import Decimal
import re
import json
import datetime

print('load location data')
location_dict = {}
with open('../../LSC2020_dataset/process_exblur/all_lifelog.txt','r') as l_file:
    next(l_file)
    for line in l_file:
        line = line.strip().split('\t')
        utc_time = datetime.datetime.strptime(line[0],"%Y-%m-%d %H:%M:%S")
        location_dict[utc_time] = line[3].strip()

print('load key image data')
img_dict = {}
with open('../../LSC2020_dataset/process_exblur/Shotmrg_newkey.txt','r') as i_file:
    next(i_file)
    for line in i_file:
        line = line.strip().split('\t')
        key_img = line[-1].strip()
        for k in line[2].split(';'):
            img_dict[k.split('/')[-1]] = key_img.split('/',3)[-1]

print('load time-image data')
time_dict = {}
tag_dict = {}
cnt = 0
with open('../../LSC2020_dataset/process_exblur/all_tags_addtags_feb28.txt','r') as t_file:
    for line in t_file:
        [img_name,utc_time] = line.split('\t')[:2]
        try:
            utc_time = datetime.datetime.strptime(utc_time,"UTC_%Y-%m-%d_%H:%M")
        except:
            if utc_time !='unknown':
                print(utc_time,img_name)
            else:
                cnt += 1
            continue
        if utc_time not in tag_dict:
            tag_dict[utc_time] = {}
        for t in line.strip().split('\t')[2:]:
            [t_name,t_score] = t.split('##')[:2]
            if t_name not in tag_dict[utc_time]:
                tag_dict[utc_time][t_name] = float(t_score)
            tag_dict[utc_time][t_name] = max(float(t_score),tag_dict[utc_time][t_name])
        if img_name.strip() in img_dict:
            time_dict[utc_time] = img_dict[img_name.strip()]
print(cnt)

print('indexing...')
timeline_schema = Schema(
date = DATETIME(stored=True,sortable=True),start_time = DATETIME(stored=True,sortable=True), 
end_time=DATETIME(stored=True),
location = TEXT(stored=True), key_image_list=TEXT(stored=True),
tags = TEXT(stored=True)
)

if not os.path.exists("timeline_index_dir"):
    os.mkdir("timeline_index_dir")

timeline_ix = index.create_in("timeline_index_dir", timeline_schema)
writer = timeline_ix.writer()

last_location = ""
last_date = ""
img_list = set()
this_tags = {}
with open('../../LSC2020_dataset/initial/newdata/lsc2020_metadata_feb12.csv','r') as m_file:
    next(m_file)
    for line in m_file:
        utc_time = line.split(',')[1]
        utc_date = datetime.datetime.strptime(utc_time.split('_')[1],"%Y-%m-%d")
        utc_time = datetime.datetime.strptime(utc_time,"UTC_%Y-%m-%d_%H:%M")
        this_location = location_dict[utc_time]
        if this_location != last_location or last_date != utc_date:
            if len(img_list):
                if not (end_time - start_time < datetime.timedelta(minutes=1) or last_location=='unknown') :
                    tags = [x[0] for x in sorted(this_tags.items(),key=lambda d:d[1],reverse=True)]
                    out_tags = [tags[0]]
                    t_len = len(tags[0])
                    for t in tags[1:]:
                        t_len += len(t)
                        if t_len>30:
                            break
                        out_tags.append(t)
                    writer.add_document(date = last_date, start_time=start_time,end_time=end_time,
                                    location=last_location, key_image_list=';'.join(img_list),
                                    tags=','.join(out_tags)+'...')
            last_location=this_location
            img_list = set()
            start_time = utc_time
            last_date = utc_date
            this_tags = {}
        end_time = utc_time
        if utc_time in tag_dict:
            for key in tag_dict[utc_time].keys():
                if key not in this_tags:
                    this_tags[key] = tag_dict[utc_time][key]
                else:
                    this_tags[key] = max(tag_dict[utc_time][key],this_tags[key])
        if utc_time in time_dict:
            img_list.add(time_dict[utc_time])
if len(img_list):
    writer.add_document(date = utc_time, start_time=start_time,end_time=end_time,
                        location=last_location, key_image_list=','.join(img_list))


writer.commit()
print('Finish timeline indexing')

print('load daily data')
daily_schema = Schema(
date = DATETIME(stored=True,sortable=True), 
calories=NUMERIC(int,decimal_places=2,stored=True),heart=NUMERIC(int,decimal_places=2,stored=True),
steps=NUMERIC(int,stored=True),
)
if not os.path.exists("daily_index_dir"):
    os.mkdir("daily_index_dir")

daily_ix = index.create_in("daily_index_dir", daily_schema)
writer = daily_ix.writer()

with open('../../LSC2020_dataset/process_exblur/timeline_daily.txt','r') as d_file:
    title = next(d_file)
    for line in d_file:
        line = line.strip().split('\t')
        utc_date = datetime.datetime.strptime(line[0],'%Y-%m-%d')
        calories = round(float(line[1]),2)
        steps = int(line[2].split('.')[0])
        heart = round(float(line[3]),2)
        writer.add_document(date=utc_date, calories=calories,heart=heart,steps=steps)

writer.commit()
print('Finish daily data indexing')
