from flask import *
from flask_wtf import FlaskForm #基类
from whoosh import analysis
from flask import session


denoise_app = Blueprint("denoise",__name__,url_prefix="/denoise/")
@denoise_app.route('/',methods=['GET','POST'])
def denoise():
    img_list = []
    Annotation = []
    No = 0
    cnt =0
    annotation = {}
    with open('../annotation_prepare/annotation_new.txt','r') as f:
        for line in f:
            line = line.split('\t')
            img_name = line[0].split('/')[-1]
            anno = line[2]
            annotation[img_name] = anno
    annotation_sort = sorted(annotation.items(),key=lambda y: y[0])
    for k in annotation_sort[380:600]:
        img_list.append([k[0]])
        Annotation.append(k[1])
    print('length: ',len(img_list))
    # if 'img_anno' not in session:
    #     session['img_anno'] = []
    #     with open('../annotation_prepare/Cluster.txt','r') as f:
    #         for line in f:
    #             # if len(session['img_anno'])<5000:
    #             #     session['img_anno'].append([' ',' ',' '])
    #             #     continue
    #             line0 = line.strip()
    #             line = line.strip().split('\t')
    #             if len(line)>2:
    #                 session['img_anno'].append([line[1],line[2],line0])
    #             else:
    #                 session['img_anno'].append([line[1],' ',line0])
    # if request.method == 'POST':
    #     No = int(request.form.get('No'))
    #     for k in range(min(10,len(session['img_anno'])-No)):
    #         flag = 1
    #         feedback = [0,0]
    #         if request.form.get('accurate'+str(k)):
    #             feedback[0] = 1
    #         if request.form.get('noise'+str(k)):
    #             feedback[1] = 1
    #             flag = 0
    #         if flag == 1:
    #             line = session['img_anno'][No+k][2]
    #             line += '\t' + str(feedback[0])+'\t'+str(feedback[1])+'\n'
    #             with open('annotation.txt','a+') as f:
    #                 f.write(line)
    #     No += 10
    #     if No>=len(session['img_anno'])-1:
    #         No = 0
    #     img_list = []
    #     Annotation = []
    #     for k in range(min(10,len(session['img_anno'])-No)):
    #         img_list += [session['img_anno'][No+k][0].split(',')]
    #         Annotation += [session['img_anno'][No+k][1]]
    # else:
    #     No  = 6030
    #     img_list = []
    #     Annotation = []
    #     for k in range(10):
    #         img_list += [session['img_anno'][No+k][0].split(',')]
    #         Annotation += [session['img_anno'][No+k][1]]
    return render_template('DenoisePage.html',content={'img_list':img_list,'Annotation':Annotation,'No':No})