import time
import whoosh
import whoosh.index as index
from whoosh import scoring,analysis
from whoosh.qparser import QueryParser
from whoosh.query import *
import argparse
import os
import gensim
import json 
import numpy as np
import re
from nltk.corpus import wordnet as wn

class MyRankfn(scoring.WeightingModel):
    '''
    Define a score function for ranking
    Consider tag confidence score and word similarity score for modeling
    n_feedback: negtive feedback from user, list of wrong ids
    '''
    use_final = True
    def __init__(self, tags_dict):
        self.tags_dict = tags_dict
        
    def supports_block_quality(self):
        return True
    
    def scorer(self, searcher, fieldname, text, qf=1):
        return MyScorer(self.tags_dict, searcher, fieldname, text, qf=qf)

    def final(self, searcher, docnum, score):
        return score        

class MyScorer(scoring.WeightLengthScorer):
    def __init__(self, tags_dict, searcher, fieldname, text, qf=1):
        self.fieldname = fieldname
        self.text = text
        self.tags_dict = tags_dict
        self.setup(searcher, fieldname, text)
        
    def score(self, matcher):
        Id = matcher.id()
        try:
            cscore = self.tags_dict[str(Id)][self.text.decode()] 
        except:
            cscore = 1
        try:
            simscore = self.simscore_dict[self.text.decode()]
        except:
            simscore = 1
        if 'Future' in self.fieldname or 'Past' in self.fieldname:
            W=0.5
        else:
            W=1
        weight_score = cscore * simscore * W
        return weight_score
    
    def _score(self, weight, length):
        return 1


def Transfer_time(Time):
    if 'early morning' in Time:
        return [4,9]
    elif 'morning' in Time:
        return [4,12]
    elif 'early afternoon' in Time:
        return [12,15]
    elif 'afternoon' in Time:
        return [12,19]
    elif 'noon' in Time :
        return [10,14]
    elif 'early evening' in Time:
        return [17,19]
    elif 'evening' in Time:
        return [17,21]
    elif 'late night' in Time:
        return [21,24]
    elif 'night' in Time:
        return [19,24]
    return [0,24]

def Query(query_terms):
    # Get query terms
    print('Search: query_terms')
    print(query_terms)
    a_time = time.time()
    my_ana = analysis.KeywordAnalyzer(commas=True,lowercase=True) | analysis.LowercaseFilter() | analysis.StopFilter()
    Or_list = []
    And_list = []
    # basic information
    for c_num in range(9):
        keyword = 'color'+str(c_num+1)
        if keyword in query_terms:
            Or_list += [Term(keyword,x.text) for x in my_ana(','.join(query_terms[keyword]))]
    # print(Or_list) 
    Range_dict = {'low':[0,100],'medium':[70,185],'high':[155,255]}
    for b in ['brightness','contrast','saturation']:
        if b in query_terms:
            Or_list += [NumericRange(b,Range_dict[query_terms[b]][0],Range_dict[query_terms[b]][1])]
    for b in ['brightness_num','contrast_num','saturation_num']:
        if b in query_terms:
            key = b.split('_')[0]
            Or_list += [NumericRange(key,query_terms[b]-5,query_terms[b]+5)]
    # Detail Description
    # time
    Time_list = []
    if 'loc_start_time' in query_terms:
        loc_start_time = query_terms['loc_start_time']
        loc_end_time = query_terms['loc_end_time']
        Time_list =  [NumericRange("loc_hour_start",loc_start_time,loc_end_time),NumericRange("loc_hour_end",loc_start_time,loc_end_time)]
    elif 'loc_time' in query_terms:
        [loc_start_time,loc_end_time] = Transfer_time(query_terms['loc_time'])
        Time_list =  [NumericRange("loc_hour_start",loc_start_time,loc_end_time),NumericRange("loc_hour_end",loc_start_time,loc_end_time)]
    if 'utc_start_time' in query_terms:
        start_time = query_terms['utc_start_time']
        end_time = query_terms['utc_end_time']
        Time_list =  [NumericRange("utc_hour_start",utc_start_time,utc_end_time),NumericRange("utc_hour_end",utc_start_time,utc_end_time)]
    elif 'utc_time' in query_terms:
        [utc_start_time,utc_end_time] = Transfer_time(query_terms['utc_time'][0])
        Time_list =  [NumericRange("utc_hour_start",utc_start_time,utc_end_time),NumericRange("utc_hour_end",utc_start_time,utc_end_time)]

    And_list = Time_list
    for keyword in (['loc_year','loc_month','loc_day','loc_weekday', \
                    'utc_year','utc_month','utc_day','utc_weekday']):
        if keyword in query_terms:
            And_list += [Or([Term(keyword,kw) for kw in query_terms[keyword]])]
    # tag
    for keyword in (['this_location','future_location','past_location', \
                     'this_activity','future_activity','past_activity', \
                     'this_tags','future_tags','past_tags']):
        if keyword in query_terms and len(query_terms[keyword])>0:
            if 'this' in keyword:
                store_key = keyword.split('_')[-1]
            else:
                store_key = keyword
            key_list = [x.split(' ') for x in query_terms[keyword]]
            if 'location' in keyword:
                # And_list += [Or([Variations("location",obj.lower()) for obj in query_terms['location']])]
                And_list += [Or([Phrase(store_key,obj) for obj in key_list ])]
            else:
                And_list += [Or([Phrase(store_key,obj) for obj in key_list ])]
    if 'is_moving' in query_terms:
        x = 'true' if query_terms['is_moving']=='yes' else 'false'
        And_list += [Term('is_moving',x)]
    if 'future_is_moving' in query_terms:
        x = 'true' if query_terms['future_is_moving']=='yes' else 'false'
        And_list += [Term('future_is_moving',x)]
    if 'past_is_moving' in query_terms:
        x = 'true' if query_terms['past_is_moving']=='yes' else 'false'
        And_list += [Term('past_is_moving',x)]
    # biometrics
    for keyword in ['elevation','speed','calories','heart','steps']:
        if keyword in query_terms:
            k_range = keyword+'_range'
            if query_terms[k_range] == 'above':
                min_num = float(query_terms[keyword])
                And_list += [NumericRange(keyword,min_num,100000000)]
            elif query_terms[k_range] == 'under':
                max_num = float(query_terms[keyword])
                And_list += [NumericRange(keyword,0,max_num)]
            else:
                [min_num,max_num] = [float(x) for x in query_terms[keyword].split(',')]
                And_list += [NumericRange(keyword,min_num,max_num)]
    b_time = time.time()
    print('query construct: ',b_time-a_time)
    #ix = index.open_dir("./blueprints/index_noscore_dir")
    a_time = time.time()
    # ix = index.open_dir("./blueprints/index_filtertag_dir")
    # ix = index.open_dir("./blueprints/index_newtagmar7_dir")
    # ix = index.open_dir("./blueprints/index_addtag28_dir")
    ix = index.open_dir("./blueprints/index_updatemar9_dir")
    b_time = time.time()
    print('index open: ',b_time-a_time)
    # end_time = time.time()
    
    a_time = time.time()
    searcher = ix.searcher(weighting=scoring.BM25F)
    f_searcher = ix.searcher(weighting=scoring.Frequency)
    b_time = time.time()
    print('searcher load: ',b_time-a_time)
        #else:
        #    searcher = ix.searcher(weighting=feedbackfn(hashing = hash_index,feedback = feedback_list))
    #with ix.searcher(weighting=MyRankfn(cscore_dict = confidence_score_dict, simscore_dict=word_similarity_dict,n_feedback=feedback)) as searcher:
        # use customized socring function
        # cscore_dict: dictionary for tag confidence score, {word(str):{Shot_id{int}:{Fieldname(str):score(float in [0,1])}}}
        # simscore_dict: dictionary for query word similarity score, {word(str):score(float in[0,1])}
    
    # negative feedback
    Not_list = []
    Exclude_shot = []
    if 'tag_feedback' in query_terms:
        Not_list += [Variations('tags',x.lower()) for x in query_terms['tag_feedback']]   
    if 'img_feedback' in query_terms:
        if len(query_terms['img_feedback']['img']):
            Exclude_shot = [ x-1 for x in query_terms['img_feedback']['img']]
        if len(query_terms['img_feedback']['location']):
            location_list = []
            for x in query_terms['img_feedback']['location']:
                stored_fields = searcher.stored_fields(x-1)
                # if stored_fields:
                #     location_list += [stored_fields['small_location']]
                    # location_list += [str(loc) for loc in stored_fields['small_location'].split(',')]
            #Not_list += [Phrase('small_location',(x.lower()).split(' ')) for x in (location_list)]
                Not_list += [Term("small_location",obj.lower()) for obj in (stored_fields['small_location']).split(',')]
        if len(query_terms['img_feedback']['time']):
            start_time_list = []
            end_time_list = []
            for x in query_terms['img_feedback']['time']:
                stored_fields = searcher.stored_fields(x-1)
                if stored_fields:
                    start_time_list.append(stored_fields['loc_hour_start'])
                    end_time_list.append(stored_fields['loc_hour_end'])
            Not_list += [NumericRange("loc_hour_start",start_time_list[i],end_time_list[i]) for i in range(len(start_time_list))]
            Not_list += [NumericRange("loc_hour_end",start_time_list[i],end_time_list[i]) for i in range(len(start_time_list))]
    if len(Or_list):
        And_list += [Or(Or_list)]
    if len(Not_list):
        And_list += [Not(x) for x in Not_list]
    myquery = And(And_list)
    myquery = myquery.normalize() 
    # search query
    id_list=[]
    print('Get query')
    print(myquery)
    print('begin search')
    a_time = time.time()
    results = searcher.search(myquery,limit=12,mask=set(Exclude_shot))
    docnums = []
    smax = 0
    for k,s in results.items():
        docnums.append(k)
        smax = max(s,smax)
    f_results = f_searcher.search(myquery,filter = set(docnums),limit=12)
    f_docnums = []
    for k,s in f_results.items():
        f_docnums.append(k)
    b_time = time.time()
    print('searching: ',b_time-a_time)
    print('end search')
    a_time = time.time()
    extra_info = []
    f_r_dict = {}
    # print(docnums)
    # print(f_docnums)
    f_smax = 0
    for n,s in f_results.items():
        f_r_dict[n] = s
        f_smax = max(s,f_smax)
    for n,s in results.items():
        id_list.append(n+1)
        stored_fields = searcher.stored_fields(n)
        want_key = ['small_location','calories','speed','heart','steps','activity','tags']
        info_dict = {key:value for key,value in stored_fields.items() if key in want_key}
        # info_dict['local_time'] = str(stored_fields['loc_date'])
        if 'tags' in info_dict:
            info_dict['tags'] = info_dict['tags'].split(',')
            if len(info_dict['tags'])>6:
                info_dict['tags'] = info_dict['tags'][:6]
            info_dict['tags'] = ','.join(info_dict['tags'])
        info_dict['f_score'] = round((f_r_dict[n]/f_smax + s/smax)/2,3)
        info_dict['score'] = s
        if 'small_location' in info_dict:
            info_dict['small_location'] = info_dict['small_location'].split(',')[0]
        extra_info.append(info_dict)
    b_time = time.time()
    print('extra info: ',b_time-a_time)
    searcher.close()
    ix.close()
    
    return id_list,extra_info

def Img_names(id_list, file_name):
    shot_file = open(file_name,'r')
    Dict = {}
    img_list = []
    img_key_list = []
    for line in shot_file:
        if not line:
            break
        info = line.strip().split("\t")
        try:
            this_id = int(info[0])
        except:
            continue
        if this_id in id_list:
            Dict[this_id] = info
    for this_id in id_list:
        info = Dict[this_id]
        img_list_t = [info[-1].split("/",3)[-1]]
        img_key_list.append(info[-1].split("/")[-1])
        for img in info[2].split(';'):
            img_list_t.append(img.split('/',3)[-1])
        img_list.append(img_list_t)
    return img_key_list, img_list


def search_main(query_terms):
    [id_list, extra_info] = Query(query_terms)
    [img_key_list,img_list] = Img_names(id_list,file_name='../LSC2020_dataset/process_exblur/Shotmrg_newkey.txt')
    shot_dict = {}
    for k in range(len(id_list)):
        shot_dict[img_key_list[k]] = id_list[k]
    return img_key_list,img_list,shot_dict,extra_info