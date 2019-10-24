from flask_wtf import FlaskForm
from wtforms import FileField,  SelectField, SubmitField, StringField

class PostForm(FlaskForm):
    file_f = FileField('Upload File')
    url = StringField('Enter URL of image')
    scale = StringField('Scale')
    w = StringField('W')
    h = StringField('H')
    compress = StringField('Compression %')
    download = SubmitField('Download')
    s3_bucket = StringField('Bucket name')
    s3_key = StringField('Access Key')
    s3_secret = StringField('Secret Key')
    s3_path = StringField('File path')
    upload = SubmitField('Upload to S3')