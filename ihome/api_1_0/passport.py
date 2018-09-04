# coding=utf-8

# 导入蓝图对象api
from . import api
# 导入flask内置的对象
from flask import request,jsonify,current_app,session,g
# 导入自定义的状态码
from ihome.utils.response_code import RET
# 导入模型类User
from ihome.models import User
# 导入登陆验证装饰器
from ihome.utils.commons import login_required
# 导入七牛云接口
from ihome.utils.image_storage import storage
# 导入数据库实例
from ihome import db, constants

# 导入正则模块,校验手机号
import re


@api.route('/sessions',methods=['POST'])
def login():
    """
    提示：
    1/获取参数,post请求,get_json()
    2/检查参数存在,如果参数存在进一步获取详细的参数信息
    mobile,password
    3/校验参数的完整性
    4/校验手机号格式,正则
    5/手机号是否已注册,查询mysql数据库
    user = User.query.filter_by(mobile=mobilbe).first()
    6/校验查询结果,校验密码
    if user is not None or user.check_password(password)
    7/缓存用户信息,使用session对象
    session['name'] = user.name
    session['mobile'] = mobile
    8/返回结果
    :return:
    """
    # pass
    # 获取参数
    user_data = request.get_json()
    # 检查参数存在
    if not user_data:
        return jsonify(errno=RET.PARAMERR,errmsg='参数错误')
    # 获取详细的参数信息,mobile/password
    mobile = user_data.get('mobile')
    password = user_data.get('password')
    # 参数完整性进行校验
    if not all([mobile,password]):
        return jsonify(errno=RET.PARAMERR,errmsg='参数缺失')
    # 对手机号格式进行检查
    if not re.match(r'1[3456789]\d{9}',mobile):
        return jsonify(errno=RET.PARAMERR,errmsg='手机号格式错误')
    # 查询数据库,确认用户的存在,以及对密码进行检查
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='查询用户信息异常')
    # 校验查询结果,并且对密码进行检查
    if user is None or not user.check_password(password):
        return jsonify(errno=RET.DATAERR,errmsg='用户名或密码错误')
    # 缓存用户信息,使用session对象
    session['user_id'] = user.id
    session['name'] = user.name
    session['mobile'] = mobile
    # 返回结果
    return jsonify(errno=RET.OK,errmsg='OK',data={'user_id':user.id})


@api.route('/user',methods=['GET'])
@login_required
def get_user_profile():
    """
    获取用户信息
    1/使用g变量获取用户id值
    2/根据id查询数据库,确认用户的存在
    3/校验查询结果
    4/返回结果
    :return:
    """
    # 获取用户id
    user_id = g.user_id
    # 查询数据库
    try:
        user = User.query.filter_by(id=user_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='查询用户信息异常')
    # 校验查询结果
    if not user:
        return jsonify(errno=RET.NODATA,errmsg='无效操作')
    # 返回用户的基本信息,调用模型类中的to_dict()方法;
    return jsonify(errno=RET.OK, errmsg='OK', data=user.to_dict())


@api.route('/user/avatar',methods=['POST'])
@login_required
def set_user_avatar():
    """
    设置用户头像
    1/获取参数,用户选择图片文件,request.files,user_id = g.user_id
    2/检查参数的存在
    3/读取图片数据,文件对象需要read/write,
    4/保存读取后的图片数据,调用七牛云接口,上传图片文件
    5/保存调用七牛云上传图片返回的图片名称,保存到数据库中
    6/提交数据,数据库中保存的是图片的相对路径
    7/拼接图片的绝对路径
    8/返回结果
    :return:
    """
    # 获取user_id
    user_id = g.user_id
    # 获取图片文件参数,avatar为表单页面的name字段名,而不是ajax中的data数据
    avatar = request.files.get('avatar')
    # 检查参数存在
    if not avatar:
        return jsonify(errno=RET.PARAMERR,errmsg='未上传图片')
    # 读取图片数据
    avatar_data = avatar.read()
    # 调用七牛云接口,实现上传头像
    try:
        # 调用七牛云返回的是图片名称,即相对路径
        image_name = storage(avatar_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR,errmsg='上传七牛云异常')
    # 保存图片的相对路径到数据库中
    try:
        # 根据id查询用户,并更新用户的头像
        User.query.filter_by(id=user_id).update({'avatar_url':image_name})
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg='保存用户头像失败')
    # 返回前端图片的绝对路径
    image_url = constants.QINIU_DOMIN_PREFIX + image_name
    # 返回结果
    return jsonify(errno=RET.OK,errmsg='OK',data={'avatar_url':image_url})


@api.route('/user/name',methods=['PUT'])
@login_required
def change_user_profile():
    """
    修改用户名
    1/获取参数,get_json()方法,user_id,name
    2/参数检查,参数的存在
    3/获取put请求数据里的name值
    4/把name信息保存到数据库中,
    User.query.filter_by(id=user_id)update({'name':name})
    5/提交数据,如果发生异常需要进行回滚
    6/更新缓存的用户信息
    7/返回结果
    :return:
    """
    user_id = g.user_id
    # 获取参数,put请求的data数据
    user_data = request.get_json()
    # 检查参数
    if not user_data:
        return jsonify(errno=RET.PARAMERR,errmsg='参数错误')
    # 获取详细的参数信息
    name = user_data.get('name')
    # 检查name
    if not name:
        return jsonify(errno=RET.PARAMERR,errmsg='用户名不能为空')
    # 更新数据库中的用户名信息
    try:
        User.query.filter_by(id=user_id).update({'name':name})
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg='更新用户名失败')
    # 更新缓存中用户信息
    session['name'] = name
    # 返回结果
    return jsonify(errno=RET.OK,errmsg='OK',data={'name':name})


@api.route('/user/auth',methods=['POST'])
@login_required
def set_user_auth():
    """
    实名认证
    1/获取参数,post请求的data数据,user_id
    2/检查参数的存在
    3/获取详细的参数信息,real_name,id_card
    4/查询数据库,执行更新用户信息
    User.query.filter_by(id=user_id,real_name=None,id_card=None).update({'real_name':real_name,'id_card':id_card})
    5/提交数据,如果发生异常需要进行回滚
    6/返回结果
    :return:
    """
    user_id = g.user_id
    # 获取参数
    user_data = request.get_json()
    # 检查参数
    if not user_data:
        return jsonify(errno=RET.PARAMERR,errmsg='参数错误')
    # 获取详细的参数信息
    real_name = user_data.get('real_name')
    id_card = user_data.get('id_card')
    # 参数的完整性检查
    if not all([real_name,id_card]):
        return jsonify(errno=RET.PARAMERR,errmsg='参数缺失')
    # 执行设置用户实名信息
    try:
        # 为了确保实名认证只执行一次,让real_name和id_card为None的情况下,执行update
        User.query.filter_by(id=user_id,real_name=None,id_card=None).update({'real_name':real_name,'id_card':id_card})
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg='保存用户实名信息失败')
    # 返回结果
    return jsonify(errno=RET.OK,errmsg='OK')


@api.route('/user/auth',methods=['GET'])
@login_required
def get_user_auth():
    """
    获取用户的实名信息
    1/获取用户的id
    2/根据id查询数据库,保存查询结果
    3/校验查询结果
    4/返回结果,data=user.auth_to_dict()
    :return:
    """
    user_id = g.user_id
    # 查询myql数据库
    try:
        user = User.query.filter_by(id=user_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='查询用户实名信息失败')
    # 校验查询结果
    if not user:
        return jsonify(errno=RET.NODATA,errmsg='无效操作')
    # 返回结果
    return jsonify(errno=RET.OK,errmsg='OK',data=user.auth_to_dict())


@api.route('/session',methods=['DELETE'])
@login_required
def logout():
    """
    退出登陆
    1/使用请求上下文对象session来实现清空用户的缓存信息
    2/返回结果

    :return:
    """
    # BUG:csrf_token missing
    # 在清除csrf_token之前,先保存csrf_token
    csrf_token = session.get('csrf_token')
    session.clear()
    # 在清空redis缓存信息后再次设置csrf_token
    session['csrf_token'] = csrf_token
    return jsonify(errno=RET.OK,errmsg='OK')


@api.route('/session',methods=['GET'])
def check_user_login():
    """
    检查用户登陆状态
    1/使用session对象来获取name,redis缓存
    2/判断获取结果,如果有登陆信息,返回name
    3/如果未登陆,默认返回false
    :return:
    """
    # 获取用户登陆信息
    name = session.get('name')
    # 判断获取结果
    if name is not None:
        return jsonify(errno=RET.OK,errmsg='true',data={'name':name})
    else:
        return jsonify(errno=RET.SESSIONERR,errmsg='false')



