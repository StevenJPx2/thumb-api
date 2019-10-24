import os
from json import loads

from flask import render_template, request, url_for, send_file, Response
from flask_restful import Resource
import pysnooper

from app import api, app
from app.thumb import (compress, compress_and_scale, load_image,
                       preprocess_img_and_upload, upload_s3, load_image_url)
from app.forms import PostForm
from werkzeug import secure_filename
from werkzeug.wsgi import FileWrapper

class ThumbGen(Resource):
    def get(self):
        s = request.args.get('s') or None
        c = request.args.get('c') or 100
        url = request.args.get('url') or None
        
        img = load_image(url)
        
        if s is not None:
            s = json.loads(s)
            img_fp = compress_and_scale(img, s, quality=int(c), return_type='b')
            
    
api.add_resource(ThumbGen, '/api')

@pysnooper.snoop()
@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():
    form = PostForm()
    if form.validate_on_submit():
        return_type = "d" if form.download.data else "u"
        
        if form.file_f.data:
            img = load_image(form.file_f.data)
            img_name = secure_filename(form.file_f.data.filename)
        
        else:
            img = load_image_url(form.url.data)
            img_name = secure_filename(form.url.data.split("/")[-1])
            
        quality = int(form.compress.data)
        scale = float(form.scale.data or 0)
        w = int(form.w.data or 0)
        h = int(form.h.data or 0)
        
        if scale and not (w or h):
            scaled_img = compress_and_scale(img, [scale], quality=quality, 
                                            return_type="b")[0]
            prefix = f"{quality}-cmp-{scale}-" if quality < 100 else f"{scale}-"
        elif (w or h) and not scale:
            scaled_img = compress_and_scale(img, [(w,h)], quality=quality, 
                                            return_type="b")[0]
            prefix = f"{quality}-cmp-{w},{h}-" if quality < 100 else f"{w},{h}-"
        else:
            scaled_img = compress_and_scale(img, [1], quality=quality, 
                                            return_type="b")[0]
            prefix = f"{quality}-cmp" if quality < 100 else ""
                
        
        scaled_img_name = prefix + img_name
        
        if return_type == "d":
            print(type(scaled_img))
            scaled_img.seek(0)
            return send_file(scaled_img, attachment_filename=scaled_img_name, as_attachment=True)
        if return_type == "u":
            img_url = upload_s3(form.s3_bucket.data, form.s3_key.data, 
                                form.s3_secret.data, form.s3_path.data, 
                                scaled_img, scaled_img_name)
            
            return render_template("index.html", form=form, url=img_url)
                
    return render_template("index.html", form=form)


@app.template_filter('autoversion')
def autoversion_filter(filename):

    fullpath = os.path.join('app/', filename[1:])
    try:
        timestamp = str(os.path.getmtime(fullpath))
    except OSError:
        return filename
    newfilename = "{0}?v={1}".format(filename, timestamp)
    return newfilename
