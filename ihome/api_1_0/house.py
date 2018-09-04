# coding=utf-8
# 导入蓝图
from . import api
# 导入redis数据库实例
from ihome import redis_store,constants,db
# 导入flask内置的对象
from flask import current_app,jsonify,g,request,session
# 导入模型类
from ihome.models import Area,House,Facility,HouseImage,User,Order
# 导入自定义的状态码
from ihome.utils.response_code import RET
# 导入登陆验证装饰器
from ihome.utils.commons import login_required
# 导入七牛云接口
from ihome.utils.image_storage import storage

# 导入json
import json
# 导入日期模块
import datetime

@api.route('/areas',methods=['GET'])
def get_areas_info():
    """
    获取城区信息:缓存----磁盘----缓存
    1/读取缓存数据库,获取城区信息
    2/判断获取结果,如果有数据,直接返回城区信息
    因为城区信息是动态加载,不同时间访问,获取到的城区数据是不同的,需要留下访问的记录;
    current_app.logger.error(e)
    current_app.logger.info('hit readis areas info')
    3/如未有数据,读取磁盘数据库
    4/判断获取结果,如果没有数据直接返回
    5/如果有数据,定义容器存储查询结果
    6/遍历查询结果,需要调用模型类中的to_dict()方法
    7/把城区信息进行序列化,
    json.dumps(areas_list)
    8/把城区存入缓存中
    9/直接返回结果
      resp = '{"errno":0,"errmsg":"OK","data":areas_json}'
      return resp
    :return:
    """
    # 尝试从redis中获取城区信息
    try:
        areas = redis_store.get('area_info')
    except Exception as e:
        current_app.logger.error(e)
        areas = None
    # 判断获取结果,如果有数据,留下访问redis数据的记录
    if areas:
        current_app.logger.info('hit redis areas info')
        # 因为redis中存储的已经是json字符串,可以直接返回
        return '{"errno":0,"errmsg":"OK","data":%s}' %areas
    # 如果缓存中没有数据,需要读取mysql数据库
    try:
        areas = Area.query.all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='查询城区信息异常')
    # 判断查询结果
    if not areas:
        return jsonify(errno=RET.NODATA,errmsg='无城区信息')
    # 定义容器,存储查询结果
    areas_list = []
    # 遍历查询结果
    for area in areas:
        areas_list.append(area.to_dict())
    # 序列化城区数据
    areas_json = json.dumps(areas_list)
    # 把城区信息写入redis缓存中
    try:
        redis_store.setex('area_info',constants.AREA_INFO_REDIS_EXPIRES,areas_json)
    except Exception as e:
        current_app.logger.error(e)
    # 返回数据
    resp = '{"errno":0,"errmsg":"OK","data":%s}' % areas_json
    return resp

@api.route('/houses',methods=['POST'])
@login_required
def save_house_info():
    """
    发布新房源
    1/获取参数,user_id,房屋的基本信息和配套设施,get_json()
    2/校验参数的存在
    3/获取详细的房屋的基本参数信息:title,price,area_id,address,room_count,acreage,unit,capacity,beds,deposit,min_days,max_days
    4/对参数的完整性进行检查,不能对facility进行处理
    5/对价格进行处理,前端一般用户输入都是以元为单位,为了确保数据的准确性,需要对价格转换,price = int ( float(price) * 100)
    6/构造模型类对象,准备存储房屋数据
    7/尝试获取房屋配套设施
    8/如果有配套设施,需要对配套设施进行校验,判断传入的配套设施是否在数据库中存储
    9/把房屋数据写入数据库中
    10/返回结果,需要返回house_id
    :return:
    """
    # 获取user_id
    user_id = g.user_id
    # 获取房屋的参数,post请求的参数
    house_data = request.get_json()
    # 检查参数的存在
    if not house_data:
        return jsonify(errno=RET.PARAMERR,errmsg='参数错误')
    # 获取房屋的详细的基本参数信息
    title = house_data.get('title') # 房屋标题
    price = house_data.get('price') # 房屋价格
    area_id = house_data.get("area_id") # 房屋城区
    address = house_data.get('address') # 房屋地址
    room_count = house_data.get('room_count') # 房屋数目
    acreage = house_data.get('acreage') # 房屋面积
    unit = house_data.get('unit') # 房屋户型
    capacity = house_data.get('capacity') # 适住人数
    beds = house_data.get('beds') # 卧床配置
    deposit = house_data.get('deposit') # 房屋押金
    min_days = house_data.get('min_days') # 最小入住天数
    max_days = house_data.get('max_days') # 最多入住天数
    # 对房屋的基本设施的参数完整性进行检查
    if not all([title,price,area_id,address,unit,room_count,acreage,capacity,beds,deposit,min_days,max_days]):
        return jsonify(errno=RET.PARAMERR,errmsg='参数缺失')
    # 对房屋的价格进行处理,前端价格一般以元为单位,后端必须以分为单位
    try:
        price = int(float(price) * 100)
        deposit = int(float(deposit)*100)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR,errmsg='房屋价格数据错误')
    # 构造模型类对象,准备存储房屋数据
    house = House()
    house.user_id = user_id
    house.area_id = area_id
    house.title = title
    house.price = price
    house.address = address
    house.room_count = room_count
    house.unit = unit
    house.capacity = capacity
    house.acreage = acreage
    house.beds = beds
    house.deposit = deposit
    house.min_days = min_days
    house.max_days = max_days
    # 尝试获取房屋配套设施
    facility = house_data.get('facility')
    # 判断配套设施是否存在
    if facility:
        # 对配套设施进行检查,确认配套设施在数据库中存在
        try:
            facilities = Facility.query.filter(Facility.id.in_(facility)).all()
            # 存储房屋配套设施
            house.facilities = facilities
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR,errmsg='查询配套设施异常')
    # 存储房屋数据
    try:
        db.session.add(house)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg='保存房屋信息失败')
    # 返回结果,返回的house_id是给后面上传房屋图片,和房屋进行关联
    return jsonify(errno=RET.OK,errmsg='OK',data={'house_id':house.id})


@api.route('/houses/<int:house_id>/images',methods=['POST'])
@login_required
def save_house_image(house_id):
    """
    保存房屋图片:
    1/获取参数,图片house_image
    2/校验参数的存在
    3/根据house_id查询数据库,确认房屋的存在
    house = House.query.get(house_id)
    4/读取图片数据
    5/调用七牛云上传图片,保存返回的图片名称(相对路径)
    6/构造模型类对象,HouseImage对象,存储图片关联的房屋,以及图片的名称
    7/临时提交数据到HouseImage对象,db.session.add(house_image)
    8/判断房屋主图片是否设置,如未设置默认添加当前的图片为房屋主图片
    9/临时提交数据到House对象,db.session.add(house)
    10/提交数据到数据库中,如果发生异常需要进行回滚
    11/拼接图片的绝对路径
    12/返回结果
    :param house_id:
    :return:
    """
    # 获取参数,post请求的图片参数
    image = request.files.get('house_image')
    # 检查参数的存在
    if not image:
        return jsonify(errno=RET.PARAMERR,errmsg='图片未上传')
    # 确认房屋的存在
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='查询房屋信息异常')
    # 校验查询结果
    if not house:
        return jsonify(errno=RET.NODATA,errmsg='无房屋数据')
    # 读取图片数据
    image_data = image.read()
    # 调用七牛云接口,实现图片上传
    try:
        image_name = storage(image_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR,errmsg='上传图片到七牛失败')
    # 构造模型类对象,准备存储房屋图片数据
    house_image = HouseImage()
    house_image.house_id = house_id
    house_image.url = image_name
    # 临时提交图片数据到数据库会话对象中
    db.session.add(house_image)
    # 判断房屋主图片是否设置,如未设置默认添加当前图片为主图片
    if not house.index_image_url:
        house.index_image_url = image_name
        # 临时提交图片数据到数据库会话对象中
        db.session.add(house)
    # 提交数据到数据库中
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg='保存图片失败')
    # 拼接图片的url
    image_url = constants.QINIU_DOMIN_PREFIX + image_name
    # 返回结果
    return jsonify(errno=RET.OK,errmsg='OK',data={'url':image_url})


@api.route('/user/houses',methods=['GET'])
@login_required
def get_user_houses():
    """
    获取用户发布的房屋信息
    1/获取用户id
    2/查询数据库,user_id
    user = User.query.get(user_id)
    houses = user.houses
    3/定义容器
    4/判断获取结果,如果有数据,存储到列表中,遍历
    5/返回结果
    :return:
    """
    # 获取用户身份
    user_id = g.user_id
    # 查询User表,确定用户的存在,其次使用关系引用,获取用户关联的房屋
    try:
        user = User.query.get(user_id)
        # 使用反向引用
        houses = user.houses
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='查询用户房屋数据失败')
    # 首先定义容器
    houses_list = []
    # 判断获取结果,如果有房屋数据,遍历
    if houses:
        for house in houses:
            houses_list.append(house.to_basic_dict())
    # 返回结果
    return jsonify(errno=RET.OK,errmsg='OK',data={'houses':houses_list})


@api.route('/houses/index',methods=['GET'])
def get_houses_index():
    """
    获取首页幻灯片信息:缓存----磁盘----缓存
    1/尝试从redis缓存中读取房屋数据
    2/如果有数据,留下访问redis数据的记录
    3/redis中存储的数据是json字符串,可以直接返回
    4/查询mysql数据库,对幻灯片的处理,默认采取房屋的成交次数,最多展示五条
    5/判断获取结果
    6/定义容器,遍历获取结果,判断房屋是否设置图片,如未设置默认不添加
    7/序列化房屋数据
    8/存入redis缓存中
    9/返回结果
    :return:
    """
    # 尝试从缓存中获取房屋数据
    try:
        ret = redis_store.get('home_page_data')
    except Exception as e:
        current_app.logger.error(e)
        ret = None
    # 判断获取结果,如果有数据,留下记录,直接返回
    if ret:
        current_app.logger.info('hit redis house index info')
        return '{"errno":0,"errmsg":"OK","data":%s}' % ret
    # 查询磁盘数据库,采取默认操作,按房屋成交次数进行排序
    try:
        houses = House.query.order_by(House.order_count.desc()).limit(constants.HOME_PAGE_MAX_HOUSES)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='查询房屋数据异常')
    # 判断获取结果
    if not houses:
        return jsonify(errno=RET.NODATA,errmsg='无房屋数据')
    # 定义容器,存储查询结果
    houses_list = []
    # 遍历查询结果,过滤没有房屋主图片的房屋
    for house in houses:
        if not house.index_image_url:
            continue
        houses_list.append(house.to_basic_dict())
    # 序列化房屋数据
    houses_json = json.dumps(houses_list)
    # 写入到redis缓存中
    try:
        redis_store.setex('home_page_data',constants.HOME_PAGE_DATA_REDIS_EXPIRES,houses_json)
    except Exception as e:
        current_app.logger.error(e)
    # 构造响应数据,返回结果
    resp = '{"errno":0,"errmsg":"OK","data":%s}' % houses_json
    return resp


@api.route('/houses/<int:house_id>',methods=['GET'])
def get_house_detail(house_id):
    """
    获取房屋详情信息
    1/首先尝试获取用户的身份,
    user_id = session.get('user_id','-1')
    2/校验house_id参数的存在
    3/尝试从redis缓存中读取房屋详情数据
    4/校验结果
    5/查询磁盘数据库
    house = House.query.get(house_id)
    6/校验查询结果,确认房屋的存在
    7/调用模型类中的hosue.to_full_dict()
    8/序列化数据
    9/存入redis缓存中
    10/构造响应数据,返回结果
    return '{"errno":0,"errmsg":"OK","data":{"user_id":%s,"house":%s}}' % (user_id,house_json)
    :return:
    """
    # 获取用户身份id
    user_id = session.get('user_id','-1')
    # 确定house_id参数的存在
    if not house_id:
        return jsonify(errno=RET.PARAMERR,errmsg='参数错误')
    # 尝试从redis缓存中获取房屋数据
    try:
        ret = redis_store.get('house_info_%s' % house_id)
    except Exception as e:
        current_app.logger.error(e)
        ret = None
    # 判断获取结果,留下记录,直接返回
    if ret:
        current_app.logger.info('hit redis house detail info')
        return '{"errno":0,"errmsg":"OK","data":{"user_id":%s,"house":%s}}' % (user_id,ret)
    # 需要查询磁盘数据库
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='查询房屋数据异常')
    # 检查查询结果
    if not house:
        return jsonify(errno=RET.NODATA,errmsg='房屋不存在')
    # 获取房屋详情数据
    try:
        # 因为to_full_dict方法里面实现房屋详情数据,需要查询数据库,所以进行异常处理
        house_data = house.to_full_dict()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='查询房屋详情数据异常')
    # 序列化房屋详情数据
    house_json = json.dumps(house_data)
    # 把房屋详情数据存入redis缓存中
    try:
        redis_store.setex('house_info_%s' % house_id,constants.HOUSE_DETAIL_REDIS_EXPIRE_SECOND,house_json)
    except Exception as e:
        current_app.logger.error(e)
    # 构造响应数据
    resp = '{"errno":0,"errmsg":"OK","data":{"user_id":%s,"house":%s}}' % (user_id,house_json)
    return resp


@api.route('/houses',methods=['GET'])
def get_houses_list():
    """
    获取房屋列表页:缓存----磁盘----缓存
    业务接口:获取参数/检查参数/业务处理/返回结果
    目的:根据用户选择的参数信息,把符合条件的房屋返回给用户.
    1/尝试获取参数:aid,sd,ed,sk,p
    区域信息/开始日期/结束日期/
    排序条件:需要给默认处理
    页数:需要给默认处理
    2/首先需要对日期进行格式化,
    datetime.strptime(start_date_str,'%Y-%m-%d')
    3/开始日期必须小于等于结束日期
    4/对页数进行格式化,page = int(page)
    5/尝试从redis缓存获取房屋的列表信息,使用的哈希数据类型,
    redis_key = 'houses_%s_%s_%s_%s' %(area_id,start_date_str,end_date_str,sort_key)
    6/判断获取结果,如果有数据,留下记录,直接返回
    7/查询磁盘数据库
    8/首先定义容器(存储查询语句的过滤条件,用来筛选出符合条件的房屋),存储查询的过滤条件,params_filter = []
    9/判断区域参数是否存在,如果存在添加到过滤条件中
    10/判断日期参数是否存在,比较用户选择的日期和数据库中订单的日期进行比较,得到满足条件的房屋
    11/过滤条件的容器里已经存储了区域信息,和满足条件的房屋
    12/判断排序条件,根据排序条件执行查询数据库操作,booking/price-inc/price-des/order_count.desc()
    houses = House.query.filter(*params_filter).order_by(House.price.desc())
    13/根据排序结果进行分页,paginate给我们的返回结果,包括总页数,房屋数据
    hosues_page = houses.paginate(page,每页的条目数,False)
    houses_list = houses_page.items
    total_page = houses_page.pages
    14/遍历房屋数据,调用模型类中的方法,获取房屋的基本数据
    15/构造响应报文
    resp = {
    errno=RET.OK,errmsg='OK',data={"houses":houses_list,"total_page":total_page,"current_page":page}
    }
    16/序列化数据:resp_json = json.dumps(resp)
    17/写入缓存中,判断用户选择的页数小于等于分页后的总页数,本质上是用户选择的页数是有数据的
    18/构造redis_key,存储房屋列表页的缓存数据,因为使用的是hash数据类型,为了确保数据的完整性,需要使用事务;开启事务,存储数据,设置有效期,执行事务/
    pip = redis_store.pipeline()
    19/返回结果resp_json

    :return:
    """

    # 获取参数,area_id,start_date_str,end_date_str,sort_key,page
    area_id = request.args.get('aid','')
    start_date_str = request.args.get('sd','')
    end_date_str = request.args.get('ed','')
    sort_key = request.args.get('sk','new') # 排序条件new为默认排序,房屋发布时间
    page = request.args.get('p','1') # 默认第一页
    # 参数处理,对日期进行处理
    try:
        # 保存格式化后的日期
        start_date,end_date = None,None
        # 判断开始日期参数的存在
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str,'%Y-%m-%d')
        # 判断结束日期的存在
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str,'%Y-%m-%d')
        # 如果开始日期和结束日期都存在的情况下,需要确认用户选择的日期至少为一天
        if start_date_str and end_date_str:
            assert start_date <= end_date
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR,errmsg='日期格式化错误')
    # 对页数进行格式化
    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR,errmsg='页数格式化错误')
    # 尝试从redis缓存中获取房屋的列表数据,因为多条数据的存储,使用的hash数据类型,首先需要键值
    try:
        # redis_key相当于hash的对象,里面存储的是页数和对应房屋数据
        redis_key = 'houses_%s_%s_%s_%s' %(area_id,start_date_str,end_date_str,sort_key)
        # 根据redis_key获取缓存数据
        ret = redis_store.hget(redis_key,page)
    except Exception as e:
        current_app.logger.error(e)
        ret = None
    # 判断获取结果,如果有数据,留下记录,直接返回
    if ret:
        current_app.logger.info('hit redis houses list info')
        # return {"errno":0,"errmsg":"OK"***}
        # ret里面已经是完整的响应报文,所以可以直接返回
        return ret
    # 查询磁盘数据库,目的:过滤条件---->查询数据--->排序---->分页,得到满足条件的房屋
    try:
        # 定义容器,存储过滤条件,主要是区域信息/日期参数
        params_filter = []
        # 判断区域信息的存在
        if area_id:
            """
            a = [1,2,3]
            b = 1
            a.append(a==b)
            a=[1,2,3,false]
            """
            # 列表中添加的是sqlalchemy对象<>
            params_filter.append(House.area_id == area_id)
        # 对日期参数的进行查询,如果用户选择了开始日期和结束日期
        if start_date and end_date:
            # 存储有冲突订单
            conflict_orders = Order.query.filter(Order.begin_date<=end_date,Order.end_date>=start_date).all()
            # 遍历有冲突的订单,获取有冲突的房屋
            conflict_houses_id = [order.house_id for order in conflict_orders]
            # 判断有冲突的房屋存在,对有冲突的房屋取反,添加不冲突的房屋
            if conflict_houses_id:
                params_filter.append(House.id.notin_(conflict_houses_id))
        # 如果用户只选择了开始日期
        elif start_date:
            conflict_orders = Order.query.filter(Order.end_date>=start_date).all()
            conflict_houses_id = [order.house_id for order in conflict_orders]
            if conflict_houses_id:
                params_filter.append(House.id.notin_(conflict_houses_id))
        # 如果用户只选择了结束日期
        elif end_date:
            conflict_orders = Order.query.filter(Order.begin_date<=end_date).all()
            conflict_houses_id = [order.house_id for order in conflict_orders]
            if conflict_houses_id:
                params_filter.append(House.id.notin_(conflict_houses_id))
        # 过滤条件实现后,执行查询排序操作,booking/price-inc/price-des/new
        # 按成交次数排序
        if 'booking' == sort_key:
            houses = House.query.filter(*params_filter).order_by(House.order_count.desc())
        # 按价格升序排序
        elif 'price-inc' == sort_key:
            houses = House.query.filter(*params_filter).order_by(House.price.asc())
        # 按价格降序排序
        elif 'price-des' == sort_key:
            houses = House.query.filter(*params_filter).order_by(House.price.desc())
        # 默认排序,按照房屋的发布时间进行排序
        else:
            houses = House.query.filter(*params_filter).order_by(House.create_time.desc())
        # 对排序结果进行分页操作,page页数/每页条目数/False表示分页异常不报错
        houses_page = houses.paginate(page,constants.HOUSE_LIST_PAGE_CAPACITY,False)
        # 获取分页后的房屋数据和总页数
        houses_list = houses_page.items
        total_page = houses_page.pages
        # 定义容器,遍历分页后的房屋数据,调用模型类中的方法,获取房屋的基本信息
        houses_dict_list = []
        for house in houses_list:
            houses_dict_list.append(house.to_basic_dict())
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg='查询房屋列表信息异常')
    # 构造响应报文
    resp = {"errno":0,"errmsg":"OK","data":{"houses":houses_dict_list,"total_page":total_page,"current_page":page}}
    # 序列化数据
    resp_json = json.dumps(resp)
    # 存储序列化后的房屋列表数据
    # 判断用户请求的页数小于分页后的总页数,即用户请求的页数有数据
    if page <= total_page:
        redis_key = 'houses_%s_%s_%s_%s' %(area_id,start_date_str,end_date_str,sort_key)
        # 可以使用事务,对多条数据同时操作
        pip = redis_store.pipeline()
        try:
            # 开启事务
            pip.multi()
            # 存储数据
            pip.hset(redis_key,page,resp_json)
            # 设置过期时间
            pip.expire(redis_key,constants.HOUSE_LIST_REDIS_EXPIRES)
            # 执行事务
            pip.execute()
        except Exception as e:
            current_app.logger.error(e)
    # 返回响应数据
    return resp_json




