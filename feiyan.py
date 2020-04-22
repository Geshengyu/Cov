import pymysql
import traceback
import json
import time
import requests
from selenium.webdriver import Chrome, ChromeOptions


def get_tencent_data():
    """
    返回历史数据和当日详细数据
    :return:
    """
    url_h5 = "https://view.inews.qq.com/g2/getOnsInfo?name=disease_h5"
    header = {'user-agent': 'Mozilla/5.0'}
    res_h5 = requests.get(url_h5, headers=header, timeout=30)
    r_h5 = json.loads(res_h5.text)  # json字符串转字典
    data_h5 = json.loads(r_h5["data"])

    url_other = "https://view.inews.qq.com/g2/getOnsInfo?name=disease_other"
    header = {'user-agent': 'Mozilla/5.0'}
    res_other = requests.get(url_other, headers=header, timeout=30)
    r_other = json.loads(res_other.text)  # json字符串转字典
    data_other = json.loads(r_other["data"])
    # dict_keys(['chinaDayList', 'chinaDayAddList', 'dailyNewAddHistory', 'dailyHistory',
    # 'wuhanDayList', 'articleList', 'provinceCompare', 'foreignList', 'globalStatis',
    # 'globalDailyHistory', 'cityStatis'])

    history = {}
    for i in data_other["chinaDayList"][7:]:
        ds = "2020." + i["date"]
        tup = time.strptime(ds, "%Y.%m.%d")  # 把时间字符串解析为时间元组
        ds = time.strftime("%Y-%m-%d", tup)  # 改变时间格式，不然插入数据库会报错，数据库是datatime类型
        confirm = i["confirm"]
        suspect = i["suspect"]
        heal = i["heal"]
        dead = i["dead"]
        history[ds] = {"confirm": confirm, "suspect": suspect, "heal": heal, "dead": dead}
    for i in data_other["chinaDayAddList"]:
        ds = "2020." + i["date"]
        tup = time.strptime(ds, "%Y.%m.%d")
        ds = time.strftime("%Y-%m-%d", tup)  # 改变时间格式，不然插入数据库会报错，数据库是datatime类型
        confirm_add = i["confirm"]
        suspect_add = i["suspect"]
        heal_add = i["heal"]
        dead_add = i["dead"]
        history[ds].update(
            {"confirm_add": confirm_add, "suspect_add": suspect_add, "heal_add": heal_add, "dead_add": dead_add})

    details = []
    update_time = data_h5["lastUpdateTime"]
    data_country = data_h5["areaTree"]
    data_province = data_country[0]["children"]
    for pro_infos in data_province:
        province = pro_infos["name"]
        for city_infos in pro_infos["children"]:
            city = city_infos["name"]
            confirm = city_infos["total"]["confirm"]
            confirm_add = city_infos["today"]["confirm"]
            heal = city_infos["total"]["heal"]
            dead = city_infos["total"]["dead"]
            details.append([update_time, province, city, confirm, confirm_add, heal, dead])

    return history, details


def get_conn():
    # 建立连接
    conn = pymysql.connect(host="localhost", user="root", password="gsy223", db="cov", charset="utf8")
    # 创建游标，默认为元组型
    cursor = conn.cursor()
    return conn, cursor


def close_conn(conn, cursor):
    if cursor:
        cursor.close()
    if conn:
        conn.close()


def update_details():
    """
    更新details表
    :return:
    """
    cursor = None
    conn = None
    try:
        li = get_tencent_data()[1]  # 0：历史数据字典， 1：最新数据列表
        conn, cursor = get_conn()
        sql = "insert into details(update_time, province, city, confirm, confirm_add, heal, dead) values(%s, %s, %s, %s, %s, %s, %s)"
        sql_query = "select %s = (select update_time from details order by id desc limit 1)"
        cursor.execute(sql_query, li[0][0])
        if not cursor.fetchone()[0]:
            print(f"{time.asctime()}开始更新最新数据")
            for item in li:
                cursor.execute(sql, item)
            conn.commit()
            print(f"{time.asctime()}更新数据完毕")
        else:
            print(f"{time.asctime()}已更新最新数据")
    except:
        traceback.print_exc()
    finally:
        close_conn(conn, cursor)


def insert_history():
    """
    插入history表：每日全国的数据
    :return:
    """
    cursor = None
    conn = None
    try:
        dic = get_tencent_data()[0]  # 0：历史数据字典， 1：最新数据列表
        print(f"{time.asctime()}开始插入历史数据")
        print(dic.items())
        conn, cursor = get_conn()
        sql = "insert into history values(%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        for k, v in dic.items():
            cursor.execute(sql, [k, v.get("confirm"), v.get("suspect"),
                                 v.get("heal"), v.get("dead"), v.get("confirm_add"), v.get("suspect_add"),
                                 v.get("heal_add"), v.get("dead_add")])
        conn.commit()
        print(f"{time.asctime()}历史数据插入完毕")
    except:
        traceback.print_exc()
    finally:
        close_conn(conn, cursor)


def update_history():
    """
    更新history表
    :return:
    """
    cursor = None
    conn = None
    try:
        dic = get_tencent_data()[0]  # 0：历史数据字典， 1：最新数据列表
        print(f"{time.asctime()}开始更新历史数据")
        print(dic.items())
        conn, cursor = get_conn()
        sql = "INSERT INTO history VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        sql_query = "SELECT confirm FROM history WHERE ds = %s"
        for k, v in dic.items():
            if not cursor.execute(sql_query, k):
                cursor.execute(sql, [k, v.get("confirm"), v.get("suspect"), v.get("heal"), v.get("dead"),
                                     v.get("confirm_add"), v.get("suspect_add"),
                                     v.get("heal_add"), v.get("dead_add")])
        conn.commit()
        print(f"{time.asctime()}历史数据更新完毕")
    except:
        traceback.print_exc()
    finally:
        close_conn(conn, cursor)


def get_baidu_hot():
    """
    获取百度热搜
    :return:
    """
    option = ChromeOptions()
    option.add_argument("--headless")  # 隐藏浏览器
    option.add_argument("--no-sandbox")

    url_baidu = "https://voice.baidu.com/act/virussearch/virussearch?from=osari_map&tab=0&infomore=1"
    browser = Chrome(options=option, executable_path="./chromedriver.exe")
    browser.get(url_baidu)
    button = browser.find_element_by_css_selector(
        '#ptab-0 > div > div.VirusHot_1-5-6_32AY4F.VirusHot_1-5-6_2RnRvg > section > div')
    button.click()
    time.sleep(1)  # 等待1秒

    words = browser.find_elements_by_xpath('//*[@id="ptab-0"]/div/div[1]/section/a/div/span[2]')
    context = [w.text for w in words]  # 获取标签内容
    print(context)
    return (context)


def update_hotSearch():
    """
    更新百度热搜
    :return:
    """
    cursor = None
    conn = None
    try:
        context = get_baidu_hot()
        print(f"{time.asctime()}热搜数据更新开始")
        conn, cursor = get_conn()
        sql = "INSERT INTO hotsearch (dt,content) VALUES(%s, %s)"
        ts = time.strftime("%Y-%m-%d %X")
        for i in context:
            cursor.execute(sql, (ts, i))
        conn.commit()
        print(f"{time.asctime()}热搜数据更新完毕")
    except:
        traceback.print_exc()
    finally:
        close_conn(conn, cursor)


if __name__ == "__main__":
    # insert_history()
    update_history()
    update_details()
    # update_hotSearch()
