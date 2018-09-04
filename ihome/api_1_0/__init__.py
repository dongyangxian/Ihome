# -*- coding:utf-8 -*-
from ihome import models
from flask import Blueprint

api = Blueprint('api', __name__)

# 把拆分出去的文件导入到创建蓝图对象的地方,和蓝图对象进行关联
from . import register,passport,house

# 请求钩子,在每次请求后执行,没有异常的情况下
@api.after_request
def after_request(response):
    """设置默认的响应报文格式为application/json"""
    # 如果响应报文response的Content-Type是以text开头，则将其改为默认的json类型
    if response.headers.get("Content-Type").startswith("text"):
        response.headers["Content-Type"] = "application/json"
    return response
