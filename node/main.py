from flask import Flask, jsonify, request, redirect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis
from hypercorn.asyncio import serve
from hypercorn.config import Config
import asyncio

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["20 per second"],
    storage_uri='redis://localhost:6379'
)
config = Config()
#配置区
redis_client = redis.Redis(host='localhost', port=6379, db=2)
mainurl = "https://yourdomain.top/api/raw/?path=/"
user_token = "user_token" #双端保持一致
config.bind = ["0.0.0.0:56789"] #可自行修改端口号
config.protocol = "h2"  # 启用HTTP2
#注意需要替换为你的证书路径
config.certfile = "./pem.pem"
config.keyfile = "./key.key"
#访问日志
config.accesslog = "access.log"

app = Flask(__name__)
limiter.init_app(app)


@app.route('/_api/update', methods=['POST'])
@limiter.limit("5 per second")
def update():
    token = request.json.get('token')
    server_id = request.json.get('server_id')
    url = request.json.get('url')
    if not token or not url or not server_id:
        return jsonify({'code':1002,'msg': 'Missing required parameters.'}), 400
    if token != user_token:
        return jsonify({'code':1002,'msg': 'Invalid token.'}), 400
    print(server_id)
    key = f'jump_{server_id}'
    redis_client.setex(key, 1200, url)
    return jsonify({'code':0,'msg': 'ok'}), 200

@app.route('/<path:url>')
@limiter.limit("30 per second")
def jump(url):
    for i in range(1, 6):
        # 从Redis中读取数据
        orig_url = None
        value = redis_client.get(f'jump_{i}')
        if value:
            orig_url = value.decode('utf-8')
            break
    if not orig_url:
        orig_url = mainurl
    backurl = orig_url + url
    return redirect(backurl)


if __name__ == '__main__':
    #app.run(debug=True)
    #app.run()
    asyncio.run(serve(app, config))
