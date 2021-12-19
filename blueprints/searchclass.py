from collections import Counter
import time as tm
import argparse
import os
import gensim
import json 
import numpy as np
import re
import whoosh
from whoosh import scoring,analysis
import whoosh.index as index
from whoosh.compat import iteritems
from whoosh.qparser import QueryParser
from whoosh.query import *
from nltk.corpus import wordnet as wn
from config import APP_STATIC_JSON
import nltk


def bm25fun(idf, tf, fl, avgfl, B, K1):
    # idf - inverse document frequency
    # tf - term frequency in the current document
    # fl - field length in the current document
    # avgfl - average field length across documents in collection
    # B, K1 - free paramters

    return idf * ((tf * (K1 + 1)) / (tf + K1 * ((1 - B) + B * fl / avgfl)))


class MyRankfn(scoring.WeightingModel):
    """Implements the BM25F scoring algorithm.
    """

    def __init__(self, floor=30,B=0.75, K1=1.2, **kwargs):
        """

        >>> from whoosh import scoring
        >>> # Set a custom B value for the "content" field
        >>> w = scoring.BM25F(B=0.75, content_B=1.0, K1=1.5)
        :param B: free parameter, see the BM25 literature. Keyword arguments of
            the form ``fieldname_B`` (for example, ``body_B``) set field-
            specific values for B.
        :param K1: free parameter, see the BM25 literature.
        """

        self.B = B
        self.K1 = K1
        self.floor = floor

        self._field_B = {}
        for k, v in iteritems(kwargs):
            if k.endswith("_B"):
                fieldname = k[:-2]
                self._field_B[fieldname] = v

    def supports_block_quality(self):
        return True

    def scorer(self, searcher, fieldname, text, qf=1):
        if not searcher.schema[fieldname].scorable:
            return WeightScorer.for_(searcher, fieldname, text)

        if fieldname in self._field_B:
            B = self._field_B[fieldname]
        else:
            B = self.B

        return MyScorer(searcher, fieldname, text, B, self.K1, qf=qf,floor=self.floor)


class MyScorer(scoring.WeightLengthScorer):
    def __init__(self, searcher, fieldname, text, B, K1, qf=1,floor=30):
        # IDF and average field length are global statistics, so get them from
        # the top-level searcher
        parent = searcher.get_parent()  # Returns self if no parent
        self.idf = parent.idf(fieldname, text)
        self.avgfl = parent.avg_field_length(fieldname) or 1

        self.B = B
        self.K1 = K1
        self.qf = qf
        self.fieldname = fieldname
        self.text = text
        self.floor = floor
        self.setup(searcher, fieldname, text)

    def score(self, matcher):
        poses = matcher.value_as("positions")
        s =  self._score(matcher.weight(), self.dfl(matcher.id()),poses)
        return s

    def block_quality(self,matcher):
        poses = matcher.value_as("positions")
        s =  self._score(matcher.block_max_weight(), matcher.block_min_length(),poses)
        return s


    def _score(self, weight, length,poses=[]):
        pos_w = sum([1/(int(x/self.floor)+1) for x in poses]) if len(poses) else 1
        if self.floor>1000:
            pow_w = weight
        s = bm25fun(self.idf, pos_w, length, self.avgfl, self.B, self.K1)
        return s



class SearchClass:
    """
    与whoosh有关的search过程
    """

    def __init__(self, ix_dir="./blueprints/index_updatemar9_dir",weighting_type='BM25F',floor=30,k=1,feedback_type="score"):
        """initializing function
        Keyword Arguments:
            ix_dir {str} -- index所在目录 (default: {"./blueprints/index_updatemar9_dir"})
            weighting_type {str} -- weighting score的类型 (default: {'BM25F'})
            floor {int} -- tag confidence 截断的台阶
            k {int} -- rerank 时是最终展示的几倍
            feedback_type {str} -- feedback的类型，score或vector
        """
        a_time = tm.time()
        self.ix = index.open_dir(ix_dir)
        self.wnl = nltk.stem.WordNetLemmatizer()
        self.wnl.lemmatize('find',pos='v')
        self.k = k
        self.feedback_type = feedback_type
        if weighting_type=='MW_tag':
            mw = scoring.MultiWeighting(scoring.BM25F(), tags=MyRankfn(floor=floor))
            self.searcher = self.ix.searcher(weighting=mw)
        elif weighting_type=='BM25F':
            self.searcher = self.ix.searcher(weighting=scoring.BM25F())
        else:
            self.searcher = ix.searcher(weighting=scoring.Frequency)
        b_time = tm.time()

    def TransferTime(self,Time):
        """time parser
        Arguments:
            Time {str} -- 时间的文本描述
        Returns:
            list -- 起止时间
        """
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

    def QueryParser(self,query_text,file_name):
        """Query Parser
        
        Arguments:
            query_text {str} -- text of query
            file_name {str} -- path of dictionary (json)
        """
        time_start = tm.time()
        with open(os.path.join(APP_STATIC_JSON,file_name),'r') as j_file:
            Info_dict =  json.load(j_file)
        query_term = {}
        Tags = {'past_tags':{},'this_tags':{},'future_tags':{}}
        grammar = r"""
        JN:{<DT>*(<CC>*<J.*>)*<N.*>+}
        NJ:{<JN><VB.*><J.*>+}
        PN:{<JN><IN>+<JN>}
        PB:{<JN><VB.><VBG><JN>}
        """
        cp = nltk.RegexpParser(grammar)
        sent_list = nltk.tokenize.sent_tokenize(query_text)
        time_end = tm.time()
        
        for sent in sent_list:
            time_start = tm.time()
            # Month, year, weekday judgement
            words = nltk.word_tokenize(sent)
            for key in ['loc_year','loc_month','loc_weekday']:
                for x in Info_dict[key]:
                    if x in words:
                        if key not in query_term:
                            query_term[key] = set()
                        if type(Info_dict[key])== dict:
                            query_term[key].add(Info_dict[key][x])
                        else:
                            query_term[key].add(x)
            for x in Info_dict['loc_time']:
                if (' ' in x and x in sent.lower()) or (' ' not in x and x in words):
                    if 'loc_time' not in query_term:
                        query_term['loc_time'] = set()
                    else:
                        query_term['loc_time'] = set(query_term['loc_time']) 
                    query_term['loc_time'].add(Info_dict['loc_time'][x])
            if 'loc_time' in query_term:
                query_term['loc_time'] = list(query_term['loc_time'])
            if 'loc_time' in query_term and len(query_term['loc_time'])>1:
                t = query_term['loc_time'][0]
                for k in query_term['loc_time'][1:]:
                    t = k if len(k)>len(t) else t
                query_term['loc_time'] = [t]
            time_end = tm.time()

            time_start = tm.time()
            sent = sent.lower()
            words = nltk.word_tokenize(sent)
            tagged = nltk.pos_tag(words)
            # time judgmement
            time = 'this'
            for word in tagged:
                if word[1]=='VBN':
                    time = 'past'
                    break
                if word[1] == 'VBD' and word[0] not in ['was','were','had']:
                    time = 'future'
                    break
            # word dictionary construct
            tree = cp.parse(tagged)
            noun_dict = {}
            verb_list = []
            for word in tagged:
                if 'V' in word[1]:
                    verb_list.append(self.wnl.lemmatize(word[0],pos='v'))
                elif word[0] in ['flight','airplane','taxi']:
                    verb_list.append(word[0])
            for subtree in tree.subtrees():
                if subtree.label() == 'NJ':
                    t = []
                    d = []
                    for word in subtree.leaves():
                        if 'NN' in word[1]:
                            t.append(word[0])
                        elif 'JJ' in word[1]:
                            d.append(word[0])
                    if len(t) != 1:
                        d += t[:-1]
                    d = list(set(d))
                    noun_dict[t[-1]] = d if (t[0] not in noun_dict or len(d) > len(noun_dict[t[0]])) else noun_dict[t[0]]
                elif subtree.label() == 'JN':
                    t = []
                    d = []
                    for word in subtree.leaves():
                        if 'NN' in word[1]:
                            t.append(word[0])
                        elif 'JJ' in word[1]:
                            d.append(word[0])
                    if len(t) != 1:
                        d += t[:-1]
                    d = list(set(d))
                    noun_dict[t[-1]] = d if (t[0] not in noun_dict or len(d) > len(noun_dict[t[0]])) else noun_dict[t[0]]
                elif subtree.label() in ['PN','PB']:
                    p = []
                    for word in subtree.leaves():
                        if word[0] not in ['is','are']:
                            if word[1] != 'DT':
                                p.append(word[0])
                    noun_dict[' '.join(p)] = []
            time_end = tm.time()
            time_start = tm.time() 
            # location process
            loc_key = time+'_location'
            for loc in Info_dict['location']:
                if ' ' in loc:
                    if loc in sent:
                        if loc_key not in query_term:
                            query_term[loc_key] = set()
                        query_term[loc_key].add(loc)
                elif len(loc) and loc in words:
                    if loc_key not in query_term:
                        query_term[loc_key] = set()
                    query_term[loc_key].add(loc)
            # activity process
            act_key = time+'_activity'
            act_dict = {'flight':'airplane,transport','airplane': 'airplane,transport', 'drive': 'transport', 
                        'walk': 'walking','walking':'walking', 'run': 'running', 'running':'running',
                        'transport': 'transport','taxi':'transport'}
            for act in verb_list:
                if act in act_dict:
                    if act_key not in query_term:
                        query_term[act_key] = set()
                    for a in act_dict[act].split(','):
                        query_term[act_key].add(a)
                    if act in ['flight','airplane','drive','ransport']:
                        if loc_key not in query_term:
                            query_term[loc_key] = set()
                        query_term[loc_key].add('transportation')
                elif act == 'shop':
                    if loc_key not in query_term:
                        query_term[loc_key] = set()
                    query_term[loc_key].add('shop')
            # tags process
            tag_key = time+'_tags'
            if tag_key not in query_term:
                query_term[tag_key] = []
            for w in noun_dict:
                if w in Info_dict['tags']:
                    for tag in Info_dict['tags'][w]:
                        if len(noun_dict[w]):
                            ltag = ' and '.join(noun_dict[w])+' '+tag
                            if ltag not in Tags[tag_key]:
                                Tags[tag_key][ltag] = []
                            Tags[tag_key][ltag].append(tag)
                            query_term[tag_key].append(ltag) 
                            for k in noun_dict[w]:
                                Tags[tag_key][ltag].append(k+' '+tag)
                        else:
                            query_term[tag_key] += [tag]
            time_end = tm.time()
            # print('term process: ',time_end - time_start,'s')
        for key in query_term:
            query_term[key] = list(set(query_term[key]))

        return query_term,Tags

    def QueryConstructor(self,query_terms):
        """Construct a query for whoosh based on query terms
        
        Arguments:
            query_terms {dict} -- query terms        
        Returns:
            myquery {whoosh.query} -- the construct query
            Exclude_shot {list} -- list of shot id to be excluded
        """
        # Get query terms
        # print('Search: query_terms')
        # print(query_terms)
        a_time = tm.time()
        Or_list = []
        And_list = []
        # basic information
        for c_num in range(9):
            keyword = 'color'+str(c_num+1)
            if keyword in query_terms:
                Or_list += [Term(keyword,x) for x in query_terms[keyword]]
        Range_dict = {'low':[0,100],'medium':[70,185],'high':[155,255]}
        for b in ['brightness','contrast','saturation']:
            # for textual query
            if b in query_terms and query_terms[b] != 'none':
                try:
                    Or_list += [NumericRange(b,Range_dict[query_terms[b]][0],Range_dict[query_terms[b]][1])]
                except:
                    print(b,query_terms[b])
        for b in ['brightness_num','contrast_num','saturation_num']:
            # for image query
            if b in query_terms:
                key = b.split('_')[0]
                Or_list += [NumericRange(key,query_terms[b]-5,query_terms[b]+5)]
        # Detail Description
        ## time
        if 'loc_start_time' in query_terms:
            loc_start_time = query_terms['loc_start_time'][0]
            loc_end_time = query_terms['loc_end_time'][0]
            And_list +=  [NumericRange("loc_hour_start",loc_start_time,loc_end_time),NumericRange("loc_hour_end",loc_start_time,loc_end_time)]
        elif 'loc_time' in query_terms:
            [loc_start_time,loc_end_time] = self.TransferTime(query_terms['loc_time'])
            And_list +=  [NumericRange("loc_hour_start",loc_start_time,loc_end_time),NumericRange("loc_hour_end",loc_start_time,loc_end_time)]
        if 'utc_start_time' in query_terms:
            start_time = query_terms['utc_start_time']
            end_time = query_terms['utc_end_time']
            And_list +=  [NumericRange("utc_hour_start",utc_start_time,utc_end_time),NumericRange("utc_hour_end",utc_start_time,utc_end_time)]
        elif 'utc_time' in query_terms:
            [utc_start_time,utc_end_time] = self.TransferTime(query_terms['utc_time'][0])
            And_list +=  [NumericRange("utc_hour_start",utc_start_time,utc_end_time),NumericRange("utc_hour_end",utc_start_time,utc_end_time)]
        for keyword in (['loc_year','loc_month','loc_day','loc_weekday', \
                        'utc_year','utc_month','utc_day','utc_weekday']):
            if keyword in query_terms:
                And_list += [Or([Term(keyword,kw) for kw in query_terms[keyword]])]
        
        ## tag, semantic
        for keyword in (['this_location','future_location','past_location', \
                        'this_activity','future_activity','past_activity', \
                        'this_tags','future_tags','past_tags']):
            if keyword in query_terms and len(query_terms[keyword])>0:
                if 'this' in keyword:
                    store_key = keyword.split('_')[-1]
                else:
                    store_key = keyword
                key_list = [x.split(' ') for x in query_terms[keyword]]
                And_list += [Or([Phrase(store_key,obj) for obj in key_list ])]
        for keyword in ['is_moving','past_is_moving','future_is_moving']:
            if keyword in query_terms:
                x = 'true' if query_terms[keyword]=='yes' else 'false'
                And_list += [Term(keyword,x)]
        
        ## biometrics
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
                    stored_fields = self.searcher.stored_fields(x-1)
                    Not_list += [Term("small_location",obj.lower()) for obj in (stored_fields['small_location']).split(',')]
            if len(query_terms['img_feedback']['time']):
                start_time_list = []
                end_time_list = []
                for x in query_terms['img_feedback']['time']:
                    stored_fields = self.searcher.stored_fields(x-1)
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
        b_time = tm.time()
        # print('query construct: ',b_time-a_time)
        # print(myquery)
        return myquery,Exclude_shot

    def QuerySearch(self,query,Exclude_shot, limit_num=10):
        """Search the Query
        
        Arguments:
            query {whoosh query} -- the structured query
            Exclude_shot {list} -- the list of shot ids to be excluded
            limit_num {int} -- number of search result
        
        Returns:
            id_list {list} -- 结果列表
            extra_info {dict} -- 结果shot包含的其他信息
        """
        a_time = tm.time()
        results = self.searcher.search(query,limit=limit_num,mask=set(Exclude_shot),terms=True)
        b_time = tm.time()
        a_time = tm.time()
        id_list=[]

        # extra_info = []
        for n,s in results.items():
            id_list.append(n+1)
        #     stored_fields = self.searcher.stored_fields(n)
        #     want_key = ['small_location','calories','speed','heart','steps','activity','tags','loc_date']
        #     info_dict = {key:value for key,value in stored_fields.items() if key in want_key}
        #     if 'tags' in info_dict:
        #         info_dict['tags'] = info_dict['tags'].split(',')
        #         if len(info_dict['tags'])>6:
        #             info_dict['tags'] = info_dict['tags'][:6]
        #         info_dict['tags'] = ','.join(info_dict['tags'])
        #     if 'small_location' in info_dict:
        #         info_dict['small_location'] = info_dict['small_location'].split(',')[0]
        #     if 'loc_date' in info_dict:
        #         info_dict['loc_date'] = str(info_dict['loc_date'])[:-3]
        #     extra_info.append(info_dict)
        # b_time = tm.time()
        # print('extra info: ',b_time-a_time)
        return results,id_list#,extra_info

    def rerank_positive(self,query_terms, results, list_length):
        if 'img_feedback' not in query_terms:
            return [0]*list_length
        NF_list =  query_terms['img_feedback']['img']
        if len(NF_list)==0:
            return [0]*list_length
        NF_stored_fields = []
        for shot_id in NF_list:
            NF_stored_fields.append(self.searcher.stored_fields(shot_id-1))
        query_add = {}
        parent = self.searcher.get_parent()  # Returns self if no parent
        idf = {}
        keyword_field = {}
        for key in query_terms:
            if 'tags' in key or 'location' in key or 'activity' in key:
                for keyword in query_terms[key]:
                    query_add[keyword] = 0
                    d_key = key
                    if key.split('_')[0] == 'this':
                        d_key = key.split('_')[1]
                    for shot in NF_stored_fields:
                        if keyword not in ','.join(shot[d_key].split(',')[:10]):
                            query_add[keyword] += 1
                    idf[keyword] = parent.idf(d_key, keyword)
                    keyword_field[keyword] = d_key
        for keyword in query_add:
            query_add[keyword] /= len(NF_stored_fields)
        new_scores = []
        cnt = 0
        for hit in results:
            new_scores.append(0)
            for keyword in query_add:
                if keyword in hit[keyword_field[keyword]]:
                    x = hit[keyword_field[keyword]]
                    # if 'tag' in keyword_field[keyword]:
                    if False:
                        tf = 0
                        for i,k in enumerate(x.split(',')):
                            if keyword in k:
                                tf += 1/(i+1)
                    else:
                        tf = x.count(keyword) / len(x.split(','))
                    new_scores[-1] += idf[keyword]*query_add[keyword] * tf
            cnt += 1
        # print('new_scores')
        # print('idf:',idf)
        # print('query_add:',query_add)
        # print(new_scores)
        return new_scores

    def rerank_negative(self, query_terms, results, list_length):
        if 'img_feedback' not in query_terms:
            return [0]*list_length
        NF_list =  query_terms['img_feedback']['img']
        if len(NF_list)==0:
            return [0]*list_length
        NF_add = {}
        parent = self.searcher.get_parent()  # Returns self if no parent
        idf = {}
        keyword_field = {}
        for shot_id in NF_list:
            stored_fields = self.searcher.stored_fields(shot_id-1)
            for key in stored_fields:
                if key in ['tags','location','activity']:
                    q_key = key if '_' in key else 'this_'+key
                    for keyword in stored_fields[key].split(',')[:10]:
                        if keyword in ['NULL','null']:
                            continue
                        if q_key not in query_terms or keyword not in query_terms[q_key]:
                            if keyword not in NF_add:
                                NF_add[keyword] = 0
                            idf[keyword] = parent.idf(key, keyword)
                            keyword_field[keyword] = key
                            NF_add[keyword] += idf[keyword] * stored_fields[key].count(keyword) / len(stored_fields[key].split(',')) 
                            keyword = keyword.split(' ')
                            if len(keyword)>1:
                                keyword = keyword[-1]
                                if keyword not in NF_add:
                                    NF_add[keyword] = 0
                                idf[keyword] = parent.idf(key, keyword)
                                keyword_field[keyword] = key
                                NF_add[keyword] += idf[keyword] * stored_fields[key].count(keyword) / len(stored_fields[key].split(','))
        for keyword in NF_add:
            NF_add[keyword] /= len(NF_list)
        new_scores = []
        cnt = 0
        for hit in results:
            new_scores.append(0)
            for keyword in NF_add:
                if keyword in hit[keyword_field[keyword]]:
                    x = hit[keyword_field[keyword]]
                    # print(keyword_field[keyword],x)
                    # if 'tag' in keyword_field[keyword]:
                    if False:
                        tf = 0
                        for i,k in enumerate(x.split(',')):
                            if keyword in k:
                                tf += 1/(i+1)
                    else:
                        tf = x.count(keyword) / len(x.split(','))
                    new_scores[-1] += idf[keyword]*NF_add[keyword] * tf
            cnt += 1
        # print('new_scores')
        # print('idf:',idf)
        # print('query_add:',NF_add)
        # print(new_scores)
        return new_scores

    def rerank_vector(self, query_terms, results, list_length,beta=1):
        if 'img_feedback' not in query_terms:
            return [0]*list_length
        NF_list =  query_terms['img_feedback']['img']
        if len(NF_list)==0:
            return [0]*list_length
        q_vector = {}
        nf_vector = {}
        parent = self.searcher.get_parent()  # Returns self if no parent
        idf = {}
        keyword_field = {}
        for key in query_terms:
            if 'tags' in key or 'location' in key or 'activity' in key:
                for keyword in query_terms[key]:
                    if keyword not in q_vector:
                        q_vector[keyword] = 0
                    q_vector[keyword] += 1
                    d_key = key
                    if key.split('_')[0] == 'this':
                        d_key = key.split('_')[1]
                    idf[keyword] = parent.idf(d_key, keyword)
                    keyword_field[keyword] = d_key
        for shot_id in NF_list:
            stored_fields = self.searcher.stored_fields(shot_id-1)
            for key in stored_fields:
                if key in ['tags','location','activity']:
                    for keyword in stored_fields[key].split(',')[:10]:
                            if keyword in ['NULL','null']:
                                continue
                            if keyword not in nf_vector:
                                nf_vector[keyword] = 0
                            idf[keyword] = parent.idf(key, keyword)
                            keyword_field[keyword] = key
                            nf_vector[keyword] += idf[keyword] * stored_fields[key].count(keyword) / len(stored_fields[key].split(','))
                            keyword = keyword.split(' ')
                            if len(keyword)>1:
                                keyword = keyword[-1]
                                if keyword not in nf_vector:
                                    nf_vector[keyword] = 0
                                idf[keyword] = parent.idf(key, keyword)
                                keyword_field[keyword] = key
                                nf_vector[keyword] += idf[keyword] * stored_fields[key].count(keyword) / len(stored_fields[key].split(','))
        q_scores = []
        nf_scores = []
        # print(q_vector)
        # print(nf_vector)
        cnt = 0
        normalize = 0
        for k in nf_vector:
            if nf_vector[k] > normalize:
                normalize = nf_vector[k]
        # print('normal:',normalize)
        for hit in results:
            q_scores.append(0)
            nf_scores.append(0)
            for keyword in q_vector:
                if keyword in hit[keyword_field[keyword]]:
                    x = hit[keyword_field[keyword]]
                    tf = x.count(keyword) / len(x.split(','))
                    q_scores[-1] += idf[keyword]*q_vector[keyword] * tf
            for keyword in nf_vector:
                if keyword in hit[keyword_field[keyword]]:
                    x = hit[keyword_field[keyword]]
                    tf = x.count(keyword) / len(x.split(','))
                    nf_scores[-1] += idf[keyword]*nf_vector[keyword] * tf
            cnt += 1
        scores = []
        # print('q_scores:',q_scores)
        for i in range(len(q_scores)):
            scores.append(q_scores[i] + nf_scores[i]/normalize*beta)
        # print(scores)
        return scores


    def Rerank(self,query_terms, results, id_list, limit_num,alpha=1,beta=-1,gamma=1):
        score_list = []
        id_list = []
        for n,s in results.items():
            id_list.append(n+1)
            score_list.append(s)
        # print(alpha,beta)
        # print(score_list)
        if self.feedback_type=='score':
            positive_score = self.rerank_positive(query_terms, results,len(score_list)) 
            negative_score = self.rerank_negative(query_terms, results,len(score_list))
            pos_max = max(positive_score) if len(positive_score) and max(positive_score)>0 else 1 
            neg_max = max(negative_score) if len(negative_score) and max(negative_score)>0 else 1 
            all_max = max(score_list) if len(score_list) and max(score_list)>0 else 1
            for i in range(len(score_list)):
                score_list[i] = (gamma*score_list[i]/all_max+alpha*positive_score[i]/pos_max + beta*negative_score[i]/neg_max)
        elif self.feedback_type=='vector':
            feedback_score = self.rerank_vector(query_terms, results, len(score_list),beta=beta)
            # print(feedback_score)
            feed_max = max(feedback_score) if len(feedback_score) and max(feedback_score)>0 else 1 
            all_max = max(score_list) if len(score_list) and max(score_list)>0 else 1
            for i in range(len(score_list)):
                score_list[i] = (gamma*score_list[i]/all_max+alpha*feedback_score[i]/feed_max)
        # print(score_list)
        new_id_list = [x for _,x in sorted(zip(score_list,id_list),reverse=True)][:limit_num]
        return new_id_list

    def Extrainfo(self, id_list):
        extra_info = []
        for shot_id in id_list:
            n = shot_id-1
            stored_fields = self.searcher.stored_fields(n)
            # if 'tags' in stored_fields:
                # print(shot_id)
                # print(stored_fields['tags'])
            want_key = ['small_location','calories','speed','heart','steps','activity','tags','loc_date']
            info_dict = {key:value for key,value in stored_fields.items() if key in want_key}
            for key in info_dict:
                if type(info_dict[key])==str:
                    info_dict[key] = info_dict[key].replace("NULL,","").replace("NULL","")
            if 'tags' in info_dict:
                info_dict['tags'] = info_dict['tags'].split(',')
                if len(info_dict['tags'])>6:
                    info_dict['tags'] = info_dict['tags'][:6]
                info_dict['tags'] = ','.join(info_dict['tags'])
            if 'small_location' in info_dict:
                info_dict['small_location'] = info_dict['small_location'].split(',')[0]
            if 'loc_date' in info_dict:
                info_dict['loc_date'] = str(info_dict['loc_date'])[:-3]
            extra_info.append(info_dict)
        return extra_info


    def QueryImgName(self,shot_list, file_name):
        """从Query得到的shot list得到对应的key image和image list
        
        Arguments:
            shot_list {list} -- a list of shot ids
            file_name {str} -- 记录shot对应 key image 和 image list 的文件路径
        
        Returns:
            img_key_list {list} -- a list of key images
            img_list {list} -- a list of (list of images)
        """
        # print(shot_list)
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
            if this_id in shot_list:
                Dict[this_id] = info
        for this_id in shot_list:
            info = Dict[this_id]
            img_list_t = [info[-1].split("/",3)[-1]]
            img_key_list.append(info[-1].split("/")[-1])
            for img in info[2].split(';'):
                if len(img_list_t) >5:
                    break
                img_list_t.append(img.split('/',3)[-1])
            img_list.append(img_list_t)
        return img_key_list, img_list

    def QueryMain(self,query_terms,limit_num=10,shot_file='../LSC2020_dataset/process_exblur/Shotmrg_newkey.txt',return_query=False,alpha=1,beta=-1,gamma=1):
        """从SearchPage或ResultPage得到query terms，返回ResultPage所需信息
        
        Arguments:
            query_terms {dict} -- query terms对应的字典
        
        Keyword Arguments:
            shot_file {str} -- shot信息存储的文件路径 (default: {'../LSC2020_dataset/process_exblur/Shotmrg_newkey.txt'})
            limit_num {int} -- number of search result (default: 10)
        
        Returns:
            img_key_list {list} -- a list of key images
            img_list {list} -- a list of (list of images)
            shot_dict {dict} -- key: key image, item: shot id
            extra_info {dict} -- 结果shot包含的其他信息
        """
        query,ex_shot = self.QueryConstructor(query_terms)
        # [results,id_list, extra_info] = self.QuerySearch(query,ex_shot,limit_num)
        results,id_list = self.QuerySearch(query, ex_shot, limit_num*self.k)
        id_list = self.Rerank(query_terms, results,id_list,limit_num,alpha,beta,gamma)
        extra_info = self.Extrainfo(id_list)
        [img_key_list,img_list] = self.QueryImgName(id_list,file_name=shot_file)
        shot_dict = {}
        for k in range(len(id_list)):
            shot_dict[img_key_list[k]] = id_list[k]
        if return_query:
            return query,img_key_list,img_list,shot_dict,extra_info
        return img_key_list,img_list,shot_dict,extra_info

    def __close__(self):
        self.searcher.close()
        self.ix.close()