import json
import nltk
import os
from config import APP_STATIC_JSON
import time as tm

def get_query_term(text,file_name):
    time_start = tm.time()
    with open(os.path.join(APP_STATIC_JSON,file_name),'r') as j_file:
        Info_dict =  json.load(j_file)
    query_term = {}
    Tags = {'past_tags':{},'this_tags':{},'future_tags':{}}
    wnl = nltk.stem.WordNetLemmatizer()

    grammar = r"""
    JN:{<DT>*(<CC>*<J.*>)*<N.*>+}
    NJ:{<JN><VB.*><J.*>+}
    PN:{<JN><IN>+<JN>}
    PB:{<JN><VB.><VBG><JN>}
    """
    cp = nltk.RegexpParser(grammar)
        
    sent_list = nltk.tokenize.sent_tokenize(text)
    time_end = tm.time()
    print('pre process: ',time_end - time_start,'s')
    
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
            # if key in query_term:
            #     query_term[key] = list(query_term[key])
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
        print('basic info: ',time_end - time_start,'s')

        time_start = tm.time()
        sent = sent.lower()
        time = 'this'
        words = nltk.word_tokenize(sent)
        tagged = nltk.pos_tag(words)
        # time judgmement
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
                verb_list.append(wnl.lemmatize(word[0],pos='v'))
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
        print('sentence process: ',time_end - time_start,'s')
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
                query_term[act_key].add(act_dict[act])
                if act in ['flight','airplane','drive','ransport']:
                    if loc_key not in query_term:
                        query_term[loc_key] = set()
                    query_term[loc_key].add('transportation')
        # tags process
        tag_key = time+'_tags'
        if tag_key not in query_term:
            query_term[tag_key] = []
        # print(word_dict)
        for w in noun_dict:
            if w in Info_dict['tags']:
                for tag in Info_dict['tags'][w]:
                    if tag not in Tags[tag_key]:
                        Tags[tag_key][tag] = [tag]
                    if len(noun_dict[w]):
                        for k in noun_dict[w]:
                            Tags[tag_key][tag].append(k+' '+tag)
                        ltag = ' and '.join(noun_dict[w])+' '+tag
                        # print(ltag)
                        Tags[tag_key][tag].append(ltag)
                        query_term[tag_key].append(ltag) 
                    else:
                        query_term[tag_key] += [tag]
        time_end = tm.time()
        print('term process: ',time_end - time_start,'s')
    
    # if 'loc_month' in query_term:
    #     query_term['loc_month'] = [x.capitalize() for x in query_term['loc_month']]
    for key in query_term:
        query_term[key] = list(set(query_term[key]))

    print('auto input:')
    print(query_term)
    print(Tags) 
    return query_term,Tags
