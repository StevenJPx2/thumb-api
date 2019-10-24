import logging
import os
from datetime import datetime
from io import BytesIO
from os import path

import boto3
import requests
from botocore.exceptions import ClientError
from PIL import Image
from tqdm import tqdm
from werkzeug.utils import secure_filename

from app import app


def l_int(*l):
    return list(map(int, l))

def scale(img, n_size, return_type='i', format='JPEG'):
    im = img.copy()
    w, h = im.size
    if type(n_size) == tuple:
        n_w, n_h = n_size
        if n_w == 0:
            im = im.resize(l_int(n_h * w/h, n_h))
        elif n_h == 0:
            im = im.resize(l_int(n_w, n_w * h/w))
        else:
            if w >= h:
                im = im.resize(l_int(n_h * w/h, n_h))
                w, h = im.size
                im = im.crop(l_int((w - n_w)/2, 0, (w + n_w)/2, n_h))
            else:
                im = im.resize(l_int(n_w, n_w * h/w))
                w, h = im.size
                im = im.crop(l_int(0, (h - n_h)/2, n_w, (h + n_h)/2))
        
    elif type(n_size) in [float, int]:
        im = im.resize(l_int(w*n_size, h*n_size), Image.ANTIALIAS)
    
    else:
        raise TypeError(f'Invalid argument type. n_size is a {type(n_size)}.')
    
    if return_type == 'i':
        return im
    elif return_type == 'b':
        temp_file = BytesIO()
        im.save(temp_file, format=format)
        return temp_file
    else:
        raise ValueError(f'Only i and b are allowed as arguments for return_type. Set argument value is {return_type}')
        

def compress(img, quality=100, format='JPEG'):
    byte_img = BytesIO()
    img.save(byte_img, optimize=True, quality=quality, subsampling=0, format=format)
    byte_img.flush()
    byte_img.seek(0)

    return Image.open(byte_img)

def compress_and_scale(img, sizes, quality=100, format='JPEG', return_type='i'):
    return [scale(compress(img, quality, format), size, return_type, format) for size in sizes]
    
def save_images(img_list, sizes, filename="picture", filetype="jpg"):
    for img, size in zip(img_list, sizes):
        if type(size) == tuple:
            img.save(f"{size[0]},{size[1]}-{filename}.{filetype}")
        else:
            img.save(f"{size}-{filename}.{filetype}")
            
def upload_s3(bucket_name, access_key, secret_key, key, obj, name):
    s3 = boto3.resource('s3', aws_access_key_id=access_key, 
                        aws_secret_access_key=secret_key)
    bucket = s3.Bucket(bucket_name)
    obj.seek(0)
    bucket.upload_fileobj(obj, f"{key}/{name}", ExtraArgs={
                          'ACL': 'public-read'})
    
    return f"https://{bucket_name}.s3.amazonaws.com/{key}/{name}"       

def preprocess_img_and_upload(img, key, bucket_name, sizes, quality=100, format='JPEG'):
    filename, filetype = os.path.splitext(secure_filename(img.filename))
    temp_file = BytesIO()
    img.save(temp_file)
    temp_file.flush()
    temp_file.seek(0)
    im = Image.open(temp_file)
    img_list = compress_and_scale(im, 
                                  sizes, 
                                  quality=quality, 
                                  format=format,
                                  return_type='b')
    
    img_urls = []
    
    for img, size in zip(img_list, sizes):
        if type(size) == tuple:
            w, h = size
            img_urls.append(upload_s3(bucket_name, key, img, f"{w},{h}-{filename}{filetype}"))
        else:
            img_urls.append(upload_s3(bucket_name, key, img, f"{size}-{filename}{filetype}"))
                
        img_urls_dict = {str(size): url for size, url in zip(sizes, img_urls)}
    
    return img_urls_dict

def load_image(fp): return Image.open(fp)

def load_image_url(img_url):

    dn_img = requests.get(img_url).content
    fp = BytesIO()
    fp.write(dn_img)
    fp.seek(0)
    
    return Image.open(fp)

def create_presigned_url(bucket_name, object_name, expiration=3600):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a presigned URL for the S3 object
    s3_client = boto3.client('s3')
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response

def create_presigned_post(bucket_name, object_name,
                          fields=None, conditions=None, expiration=3600):
    """Generate a presigned URL S3 POST request to upload a file

    :param bucket_name: string
    :param object_name: string
    :param fields: Dictionary of prefilled form fields
    :param conditions: List of conditions to include in the policy
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Dictionary with the following keys:
        url: URL to post to
        fields: Dictionary of form fields and values to submit with the POST
    :return: None if error.
    """

    # Generate a presigned S3 POST URL
    s3_client = boto3.client('s3')
    try:
        response = s3_client.generate_presigned_post(bucket_name,
                                                     object_name,
                                                     Fields=fields,
                                                     Conditions=conditions,
                                                     ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL and required fields
    return response