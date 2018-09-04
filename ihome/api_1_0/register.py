# coding=utf-8

# 导入蓝图对象api
from datetime import datetime

from . import api
# 导入captcha扩展包
from ihome.utils.captcha.captcha import captcha
# 导入redis数据库实例
from ihome import redis_store,constants,db
# 导入flask内置的对象current_app
from flask import current_app,jsonify,make_response,request,session
# 导入自定义的状态码
from ihome.utils.response_code import RET
# 导入模型类User
from ihome.models import User
# 导入云通讯扩展
from ihome.utils import sms

# 导入正则模块,校验手机号
import re
# 导入random模块,用来生成短信码
import random


@api.route('/imagecode/<image_code_id>',methods=['GET'])
def generate_image_code(image_code_id):
    """
    生成图片验证码
    1/导入使用captcha扩展包,生成图片验证码,name/text/image
    2/在服务器保存图片验证码,保存到redis中,
    3/如果保存失败,返回错误信息,记录日志current_app
    4/返回图片,使用make_response对象
    :param image_code_id:
    :return:
    """
    # 生成图片验证码
    name,text,image = captcha.generate_captcha()
    # 保存图片验证码到redis中
    try:
        redis_store.setex('ImageCode_' + image_code_id,constants.IMAGE_CODE_REDIS_EXPIRES,text)
    except Exception as e:
        # 记录错误日志信息
        current_app.logger.error(e)
        # 返回错误信息
        return jsonify(errno=RET.DBERR,errmsg='保存图片验证码失败')
    # 如果未发生异常,执行else
    else:
        # 使用响应对象返回图片
        response = make_response(image)
        # 设置响应的数据类型
        response.headers['Content-Type'] = 'image/jpg'
        # 返回结果
        return response


@api.route('/smscode/<mobile>',methods=['GET'])
def send_sms_code(mobile):
    """
    发送短信:获取参数---检查参数---业务处理(查询数据)---返回结果
    1/获取参数,mobile,text(图片验证码),id(图片验证码编号)
    2/校验参数的完整性
    3/校验手机号,正则校验手机号
    4/获取本地存储的真实图片验证码
    5/判断获取结果是否存在
    6/删除已经读取过的图片验证码,图片验证码只能获取一次
    7/比较图片验证码是否一致
    8/发送短信,云通讯只能提供网络服务,短信内容需要自定义,随机数
    9/生成一个短信验证码,六位数的随机数,random.randint()
    10/存储短信验证码到redis数据库中
    11/准备发送短信,判断用户是否已注册,然后调用sms.CCP()
    12/保存发送结果,判断发送是否成功
    13/返回结果
    :param mobile:
    :return:
    """
    # 获取参数,get请求,text为用户输入的图片验证码内容,id为图片验证码编号
    image_code = request.args.get('text')
    image_code_id = request.args.get('id')
    # 校验参数的完整性,any判断一个
    if not all([mobile,image_code,image_code_id]):
        return jsonify(errno=RET.PARAMERR,errmsg='参数不完整')
    # 参数检查,首先检查手机号
    # a = compile()把具体的数据编译成一个对象,match()从前往后,search()搜索,findall()查询所有,sub()查询替换
    # \d,\D,\w(a-zA-Z0-9_)\W,.+*?
    if not re.match(r'1[3456789]\d{9}',mobile):
        return jsonify(errno=RET.PARAMERR,errmsg='手机号格式错误')
    # 获取真实的图片验证码
    try:
        real_image_code = redis_store.get('ImageCode_' + image_code_id)
        # real_image_code = real_image_code.decode('utf-8')
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='获取图片验证码失败')
    # 判断获取结果
    if not real_image_code:
        return jsonify(errno=RET.NODATA,errmsg='图片验证码已过期')
    # 删除图片验证码,因为只能读取一次
    try:
        redis_store.delete('ImageCode_' + image_code_id)
    except Exception as e:
        current_app.logger.error(e)
    # 比较图片验证码是否一致,需要忽略大小写
    if real_image_code.lower() != image_code.lower():
        return jsonify(errno=RET.DATAERR,errmsg='图片验证码不一致')
    # 判断手机号是否已注册
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='查询数据库异常')
    else:
        # 判断查询结果,用户是否存在
        if user is not None:
            return jsonify(errno=RET.DATAEXIST,errmsg='手机号已注册')
    # 生成短信随机数,六位数
    sms_code = '%06d' % random.randint(1,999999)
    print('生成的短信验证码：', sms_code)
    # 保存短信验证码,到redis中
    try:
        redis_store.setex('SMSCode_' + mobile,constants.SMS_CODE_REDIS_EXPIRES,sms_code)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='保存数据异常')
    # 调用云通讯扩展,准备发送短信,调用第三方扩展一般都需要异常处理
    # try:
    #     send_sms = sms.CCP()
    #     result = send_sms.send_template_sms(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES/60], 1)
    # except Exception as e:
    #     current_app.logger.error(e)
    #     return jsonify(errno=RET.THIRDERR,errmsg='发送短信异常')
    # # 判断返回结果,表达式中变量和数据比较,建议变量写后面;
    # if 0 == result:
    # # if result == 0:
    #     return jsonify(errno=RET.OK,errmsg='发送成功')
    # else:
    #     return jsonify(errno=RET.THIRDERR,errmsg='发送失败')
    return jsonify(errno=RET.OK, errmsg='发送成功')


@api.route('/users', methods=['POST'])
def register():
    """
    注册:
    简单提示：
    获取参数
    校验参数
    查询数据
    模型对象
    提交数据
    保存状态
    返回结果
    :return:
    """
    # TODO 完成注册代码
    params_dict = request.json
    mobile = params_dict.get("mobile")
    password = params_dict.get("password")
    sms_code = params_dict.get("sms_code")

    if not all([mobile, password, sms_code]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    # 验证手机号的格式
    if not re.match("^1[356789][0-9]{9}$", mobile):
        return jsonify(erron=RET.PARAMERR, errmsg="手机格式有误")
    # 查询数据库，是否存在该手机号
    try:
        user = User.query.filter_by(mobile=mobile).first()
        if user:
            return jsonify(errno=RET.DATAEXIST, errmsg="用户已存在")
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询数据库异常')

    # 根据手机号的验证编码，取出数据库的验证码，进行比较
    try:
        real_sms_code = redis_store.get('SMSCode_' + mobile)
        if real_sms_code:
            redis_store.delete("sms_%s" % mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="获取短信验证码数据库异常")
    if not real_sms_code:
        # 没有值表示短信验证码过期了
        return jsonify(errno=RET.NODATA, errmsg="短信验证码过期")
    if sms_code != real_sms_code:
        return jsonify(errno=RET.PARAMERR, errmsg="短信验证码填写错误")

    # 创建用户对象 给对应属性赋值
    user = User()

    user.mobile = mobile
    user.name = mobile

    # 需要将加密的密码加密
    user.password = password

    # 记录一下最后一次保存的登录时间
    user.create_time = datetime.now()

    # 保存数据
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 回滚
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存用户对象到数据库异常")

    # 使用session保存当前的数据，直接进行登录
    session["user_id"] = user.id
    session["mobile"] = user.mobile
    session["name"] = user.name

    # 返回响应对象
    return jsonify(errno=RET.OK, errmsg="注册成功！")