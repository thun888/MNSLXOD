import os
import requests
from flask import Flask, jsonify, send_file, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlite3
import datetime
import threading
import time
from hypercorn.asyncio import serve
from hypercorn.config import Config
import asyncio

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["40 per second"],
    storage_uri='redis://localhost:6379'
)
config = Config()
###配置区###
config.bind = ["0.0.0.0:45678"]  # 自行更改端口
config.protocol = "h2"  # 启用HTTP2
#注意需要替换为你的证书路径，不用就连带下面两行注释掉
config.certfile = "./pem.pem"
config.keyfile = "./key.key"
#访问日志目录
config.accesslog = "access.log"
server_id = 1
mainurl = "https://yuordomain.top/api/raw/?path=/"
jumpurl = "https://jumpurl/"
apiurl = "http://apiurl/"
backupurl = "http://backupurl/"
token = "token"

app = Flask(__name__)
limiter.init_app(app)

def savetodatabase(nowtime,outdata,indata):
    conn = sqlite3.connect('data.db')
    cursor_daily = conn.cursor()
    cursor_daily.execute("SELECT COUNT(*) FROM daily WHERE date=?", (nowtime,))
    if cursor_daily.fetchone()[0] == 0:
        cursor_daily.execute("INSERT INTO daily (date, get, traffic_out, traffic_in) VALUES (?, ?, ?, ?)", (nowtime, 1, outdata, indata))
    else:
        cursor_daily.execute("UPDATE daily SET traffic_out = traffic_out + ?, get = get + ?, traffic_in = traffic_in + ? WHERE date=?", (outdata, 1, indata, nowtime))

    cursor_total = conn.cursor()
    cursor_total.execute("UPDATE total SET traffic_out = traffic_out + ?, get = get + ?, traffic_in = traffic_in + ?", (outdata, 1, indata))
    conn.commit()

    return

@app.route('/_api/status')
@limiter.limit("1 per second")
def get_status():
    uptime = str(datetime.datetime.now() - start_time)
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT get,traffic_in,traffic_out FROM total")
    result = cursor.fetchone()
    get = result[0]
    traffic_in = result[1]
    traffic_out = result[2]
    # 构造状态信息
    status = {
        'server_id': server_id,
        'uptime': uptime,
        'traffic_out': traffic_out,
        'traffic_in': traffic_in,
        'get': get
    }

    return jsonify(status)

@app.route('/_api/traffic')
@limiter.limit("1 per second")
def get_traffic_daily():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM "daily" ORDER BY "date" DESC LIMIT 0,14')

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    data = []
    for row in rows:
        data.append({
            'date': row[0],
            'traffic_out': row[3],
            'traffic_in': row[2]
        })

    return jsonify(data)

@app.route('/_api/cache_clean')
@limiter.limit("1 per second")
def cache_clean():
    day = int(request.args.get('day', 1))
    size = clear_old_files(0)
    status = {
        'size': size,
    }

    return jsonify(status)

@app.route('/<path:url>')
@limiter.limit("40 per second")

def download_file(url):
    #print(url)
    if url == "favicon.ico":
        url = "mount/pic/favicon.webp"
    cache_path = os.path.join('tmp', url)
    nowtime = datetime.datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(cache_path):
        file_size = os.path.getsize(cache_path)
        savetodatabase(nowtime,file_size,0)
        return send_file(cache_path)

    primary_url = mainurl + url
    response = requests.get(primary_url, allow_redirects=True)

    if response.status_code == 200:
        try:
            os.makedirs(os.path.dirname(cache_path))
        except OSError:
            pass
        with open(cache_path, 'wb') as f:
            f.write(response.content)

        file_size = os.path.getsize(cache_path)
        savetodatabase(nowtime,file_size,file_size)
        return send_file(cache_path)

    print("从原站获取"+url)
    secondary_url = backupurl + url
    response = requests.get(secondary_url, allow_redirects=True)

    if response.status_code == 200:
        try:
            os.makedirs(os.path.dirname(cache_path))
        except OSError:
            pass
        with open(cache_path, 'wb') as f:
            f.write(response.content)

        file_size = os.path.getsize(cache_path)
        savetodatabase(nowtime,file_size,file_size)
        return send_file(cache_path)

    else:
        error_msg = 'Failed to download file. URLs: %s' % (primary_url)
        app.logger.error(error_msg)
        return jsonify({'error': error_msg}), 404
    
def get_directory_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            total_size += os.path.getsize(file_path)
    return total_size

def clear_old_files(days):
    total_deleted_size = 0  # 用于记录删除文件的总大小
    # 获取当前时间
    current_time = datetime.datetime.now()

    # 计算1天前的时间
    one_day_ago = current_time - datetime.timedelta(days=days)

    # 遍历目录中的所有文件
    for root, dirs, files in os.walk(current_directory):
        for file in files:
            file_path = os.path.join(root, file)

            modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

            # 如果文件的修改时间早于1天前的时间，则删除文件
            if modification_time < one_day_ago:
                file_size = os.path.getsize(file_path)  # 获取文件大小
                total_deleted_size += file_size  # 累加删除文件的大小
                os.remove(file_path)

    return total_deleted_size

def delcache():
    size = get_directory_size(current_directory)
    if size > 5368709120:
        clear_old_files(10)                       
def update():
    data = {
        "token": token,
        "server_id": server_id, 
        "url": jumpurl 
    }

    # 定义目标网址
    target_url = apiurl + "_api/update"
    # 发送post请求，并获取响应
    response = requests.post(target_url, json=data)       
    return response                      
def run_timer():
    while True:                                                                                                                                                                              
        # 每15分钟执行一次
        time.sleep(15 * 60)
        threading.Thread(target=delcache).start()
        threading.Thread(target=update).start()

if __name__ == '__main__':
    start_time = datetime.datetime.now()
    if not os.path.exists('tmp'):
        os.mkdir('tmp')
    current_directory = os.path.join(os.getcwd(), 'tmp')
    print("缓存目录为:",current_directory)
    update()
    #print(start_time)
    timer_thread = threading.Thread(target=run_timer)
    timer_thread.daemon = True
    timer_thread.start()
    # app.run(debug=True,host='0.0.0.0')
    # app.run(host='0.0.0.0')
    asyncio.run(serve(app, config))  # 启动服务器