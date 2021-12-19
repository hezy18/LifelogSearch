import time
import whoosh
import whoosh.index as index
from whoosh import scoring
from whoosh.qparser import QueryParser
from whoosh.query import *
from whoosh import index,analysis
import argparse
import os
import gensim
import json 
import numpy as np
import re
from nltk.corpus import wordnet as wn
from scipy import spatial

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

class feedbackfn(scoring.BM25F):
    use_final = True

    def __init__(self,hashing,feedback,B=0.75,K1=1.5,qf=1):
        super().__init__(B,K1,qf=qf)
        self.hashing = hashing
        self.feedback = feedback
    
    def final(self,searcher,docnum,score):
        cos_dis = 1
        if docnum+1 in self.feedback[0] or docnum+1 in self.feedback[1]:
            print(docnum)
            score = 0.1
        else:
            this = self.hashing[docnum+1]
            for shot_id in self.feedback[1]:
                cos_dis = min(cos_dis, spatial.distance.cosine(this,self.hashing[shot_id]))
            score *= cos_dis
        return score

def Transfer_time(Time):
    if 'morning' in Time:
        return [4,12]
    if 'noon' in Time and 'afternoon' not in Time:
        return [10,14]
    if 'afternoon' in Time:
        return [12,19]
    if 'evening' in Time:
        return [17,21]
    if 'night' in Time:
        return [19,24]
    return [0,24]

def Query(query_terms,use_feedback,feedback_list=[[],[]],hash_index={}):
    # Get query terms
    print(query_terms)
    print(feedback_list)
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
        [utc_start_time,utc_end_time] = Transfer_time(query_terms['utc_time'])
        Time_list =  [NumericRange("utc_hour_start",utc_start_time,utc_end_time),NumericRange("utc_hour_end",utc_start_time,utc_end_time)]

    And_list = Time_list
    for keyword in (['loc_year','loc_month','loc_day','loc_weekday', \
                    'utc_year','utc_month','utc_day','utc_weekday', \
                    'companion','future_companion','past_companion']):
        if keyword in query_terms:
            And_list += [Term(keyword,query_terms[keyword])]
    for keyword in (['location','future_location','past_location', \
                     'activity','future_activity','past_activity', \
                     'tags','future_tags','past_tags']):
        if keyword in query_terms and len(query_terms[keyword])>0:
            And_list += [Or([Variations(keyword,obj) for obj in (query_terms[keyword])])]
    if 'is_moving' in query_terms:
        x = 'true' if query_terms['is_moving']=='yes' else 'false'
        And_list += [Term('is_moving',x)]
    for keyword in ['elevation','speed','calories','heart','steps']:
        if keyword in query_terms:
            k_range = keyword+'_range'
            if query_terms[k_range] == 'above':
                min_num = float(query_terms[keyword])
                And_list += [NumericRange(keyword,min_num,100000000)]
            elif query_terms[k_range] == 'below':
                max_num = float(query_terms[keyword])
                And_list += [NumericRange(keyword,0,max_num)]
            else:
                [min_num,max_num] = [float(x) for x in query_terms[keyword].split('and')]
                And_list += [NumericRange(keyword,min_num,max_num)]
    myquery = And(And_list)    
    # search query
    id_list=[]
    # ix = index.open_dir("../search/index_dir_new")
    ix = index.open_dir("index_noscore_dir")
    print(myquery)
    if True:
        if not use_feedback:
            searcher = ix.searcher(weighting=scoring.BM25F)
        else:
            searcher = ix.searcher(weighting=feedbackfn(hashing = hash_index,feedback = feedback_list))
    #with ix.searcher(weighting=MyRankfn(cscore_dict = confidence_score_dict, simscore_dict=word_similarity_dict,n_feedback=feedback)) as searcher:
        # use customized socring function
        # cscore_dict: dictionary for tag confidence score, {word(str):{Shot_id{int}:{Fieldname(str):score(float in [0,1])}}}
        # simscore_dict: dictionary for query word similarity score, {word(str):score(float in[0,1])}
        print('begin search')
        results = searcher.search(myquery,limit=10)
        for n,s in results.items():
            id_list.append(n+1)
    #finally:
    searcher.close()
    ix.close()
    return id_list

def Img_names(id_list, file_name):
    shot_file = open(file_name,'r')
    Dict = {}
    img_list = []
    for line in shot_file:
        if not line:
            break
        info = line.strip().split("\t")
        try:
            this_id = int(info[0])
        except:
            continue
        if this_id in id_list:
            Dict[this_id] = [info[-1].split("/",3)[-1]]
            for img in info[2].split(';'):
                Dict[this_id].append(img.split('/',3)[-1])
    for key in id_list:
        img_list.append( Dict[key] )
    return img_list


def search_main(query_terms,use_feedback,feedback=[[],[]],hashing_dict={}):
    id_list = Query(query_terms,use_feedback,feedback,hashing_dict)
    return id_list,Img_names(id_list,file_name='../../LSC2020_dataset/process_exblur/Shotmrg_newkey.txt')

def Get_query(New_query,query_term,feedback_list):
    New_list = New_query.strip().split(";")
    Wrong_list = [[],[]]
    for term in New_list:
        term = term.split("#")
        if term[0] =='Add':
            if term[1] in query_terms:
                query_terms[term[1]] |= set(re.split(',',term[2].strip()))
            else:
                query_terms[term[1]] = set(re.split(',',term[2].strip()))
        elif term[0] == 'Del':
            if term[1] in query_terms:
                query_terms[term[1]] -= set(re.split(',',term[2].strip()))
                if len(query_terms[term[1]])==0:
                    query_terms.pop(term[1])
        elif term[0] == 'Alter':
            query_terms[term[1]] = term[2]
        elif term[0] == 'one_wrong':
                Wrong_list[0] = [int(x) for x in term[1].strip().split(',')]
        elif term[0] == 'all_wrong':
                Wrong_list[1] = [int(x) for x in term[1].strip().split(',')]
    feedback_list[0] += Wrong_list[0]
    feedback_list[1] += Wrong_list[1]
    return query_terms, feedback_list

if __name__ =='__main__':
    # # load hash dict
    hash_index={}
    # with open('../hashing/shotinfo_hash.txt','r') as hash_file:
    #     shot_id = 1
    #     for line in hash_file:
    #         hash_index[shot_id] = [int(x) for x in line.strip()]
    #         shot_id += 1
    query_terms = {}
    feedback_list=[[],[]]
    user_query = input("Add query to search\n(example:Add#Fieldname#value1,value2;Del#Fieldname#value1;one_wrong#1,2;all_wrong#3,4)\n")
    while "endsearch" not in user_query:
        if "clearall" in user_query:
            query_terms = {}
            user_query = input("Add query to search(Add#Fieldname#'value1','value2';Del#Fieldname#'value1';one_wrong#1,2;all_wrong#3,4)\n")
            continue
        [query_terms,feedback_list] = Get_query(user_query,query_terms,feedback_list)
        # id_list,img_shot_list = search_main(query_terms,True,feedback_list,hash_index)
        id_list,img_shot_list = search_main(query_terms,False)
        with open('../result.txt','w') as result_file:
            for img_list in img_shot_list:
                for img in img_list:
                    result_file.write(img+'\n')
                result_file.write('shotend\n')
        
        user_query = input("Add query to search(Add#Fieldname#'value1','value2';Del#Fieldname#'value1';one_wrong#1,2;all_wrong#3,4)\n")