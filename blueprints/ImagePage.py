from flask import *
from flask_wtf import FlaskForm #基类
from whoosh import analysis
from flask import session
from . import search,auto_input
import nltk
import numpy as np
import cv2
import json
import calendar
from werkzeug.utils import secure_filename
import os
import requests as rq 


def get_tags(img_path):
    r = rq.post(
        "https://api.deepai.org/api/densecap",
        files={
            'image': open(img_path, 'rb'),
        },
        headers={'api-key': '70e29f5f-b3e6-4ddf-9aac-c4a1cf3a3c99'}
        )
    result = r.json()
    tags = set()
    for concepts in result['output']['captions']:
        caption = concepts['caption']
        sentence = nltk.sent_tokenize(caption)
        word_list = nltk.pos_tag(nltk.word_tokenize(sentence[0]))
        score = round(float(concepts['confidence']),3)
        for word in word_list:
            if word[1] in ['NN','NNS','NNP']:
                tag = word[0]
                break
        tags.add(tag)
    return list(tags)

def domain_color(hsv):
    '''
    input : numpy matrix of image
    output : a list of domain color in 9 areas: [(1row,1col),(1row,2col),(1row,3col)],each is represented by one name
    '''
    [width,height,c] = hsv.shape
    # 黑、灰、白、红1、红2、橙、黄、绿、青、蓝、紫
    range_min=np.array([[0,0,0],[0,0,47],[0,0,151],[0,43,46],[156,43,46],[11,43,46],
                        [26,43,46],[35,43,46],[78,43,46],[100,43,46],[125,43,46]])
    range_max=np.array([[180,255,46],[180,43,150],[180,30,255],[10,255,255],[180,255,255],[25,255,255],
                       [34,255,255],[77,255,255],[99,255,255],[124,255,255],[155,255,255]])
    range_name = ['black','gray','white','red','red','orange','yellow','green','cyan','blue','purple']
    mask = []
    
    for color_idx in range(len(range_name)):
        mask.append(cv2.inRange(hsv,range_min[color_idx],range_max[color_idx]))
    
    area_w = [0,int(width/3),int(width/3)*2,width]
    area_h = [0,int(height/3),int(height/3)*2,height]
    
    domain_color = []
    for i in range(3):
        for j in range(3):
            sum_color = []
            for k in range(len(range_name)):
                sum_color.append(cv2.countNonZero(mask[k][area_w[i]:area_w[i+1],area_h[j]:area_h[j+1]]))
            # red area
            sum_color[3] += sum_color[4]
            domain_color.append(range_name[np.argmax(sum_color)])
        
    return domain_color

def overall_info(hls):
    '''
    input : numpy matrix of image
    output: [brightness, contrast, saturation]
    '''
    brightness = np.around(np.mean(np.mean(hls[:,:,1])),2)
    saturation = np.around(np.mean(np.mean(hls[:,:,2])),2)
    contrast = np.around(np.min(np.mean(hls[:,:,1])) - np.min(np.min(hls[:,:,1])),2)
    
    return [brightness, contrast, saturation]

def basic_info(img_name):
    img = cv2.imread(img_name)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
    return [domain_color(hsv),overall_info(hls)]

img_app = Blueprint("image_search",__name__,url_prefix="/image_search/")
@img_app.route('/',methods=['GET','POST'])
def img_search():
    if request.method =='POST' and request.form.get("uploadImage"):
        f = request.files['chooseImage']
        print(f)
        if f:
            filename = secure_filename(f.filename)
            types = ['jpg','png','tif','jpeg']
            if filename.split('.')[-1].lower() in types:
                uploadpath = os.path.join('static/upload_img',filename)
                f.save(uploadpath)
                session['uploadpath'] = uploadpath
                return render_template('ImagePage.html',imgpath=uploadpath)
            else:
                return render_template('ImagePage.html',imgpath='static/LSC2020_images/2015-02-23/b00000000_21i6bq_20150223_070647e.jpg')
    elif request.method=='POST' and request.form.get("search"):
        t = request.form.getlist("search_choice")
        if len(t)==0:
            return render_template('ImagePage.html',imgpath=sesion['uploadpath'])
        query_term = {}
        if 'content' in t:
            [color_list,info_list] = basic_info(session['uploadpath'])
            for i,color in enumerate(color_list):
                query_term['color'+str(i+1)] = [color]
            for num,key in zip(info_list,['brightness_num','contrast_num','saturation_num']):
                query_term[key] = num
        if 'semantic' in t:
            tags = get_tags(session['uploadpath'])
            query_term['this_tags'] = tags
        [img_key_list, img_all_list,shot_id_dict,extra_info] = search.search_main(query_term)#,use_feedback=False,feedback=feedback_id)
        print(img_key_list) 
        return render_template('ImageResultPage.html',result={'query_img':session['uploadpath'],'img_key_list':img_key_list,'img_all_list':img_all_list,'extra_info':extra_info})
    else:
        #return render_template('ImagePage.html',imgpath='preview of uploaded image')
        return render_template('ImagePage.html',imgpath='static/LSC2020_images/2015-02-23/b00000002_21i6bq_20150223_070809e.jpg')