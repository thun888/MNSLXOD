<?php
// 连接 Redis 服务器
$redis = new Redis();
$redis->connect('127.0.0.1', 6379);
$redis->select(2);
//token
$user_token = "yourtoken";
//主服务器url
$mainurl = "https://yourdomain.top/api/raw/?path=/";

// 定义限制器类
class Limiter {
    private $limits;
    private $key_func;
    private $requests;

    public function __construct($key_func, $default_limits) {
        $this->limits = $default_limits;
        $this->key_func = $key_func;
        $this->requests = array();
    }

    public function limit($route, $limit) {
        if (!isset($this->requests[$route])) {
            $this->requests[$route] = array();
        }
        $key = call_user_func($this->key_func);
        if (!isset($this->requests[$route][$key])) {
            $this->requests[$route][$key] = array();
        }
        array_push($this->requests[$route][$key], time());
        while (count($this->requests[$route][$key]) > 0 && time() - $this->requests[$route][$key][0] > 1) {
            array_shift($this->requests[$route][$key]);
        }
        if (count($this->requests[$route][$key]) > $limit) {
            http_response_code(429);
            die('Too Many Requests');
        }
    }
}

// 定义获取客户端 IP 地址的函数
function get_remote_address() {
    return $_SERVER['REMOTE_ADDR'];
}

// 初始化限制器
$limiter = new Limiter('get_remote_address', array('40 per second'));


// 定义 update 路由
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $_SERVER['REQUEST_URI'] === '/_api/update') {
    // 检查请求速率
    $limiter->limit('/_api/update', 5);

    // 获取请求参数
    $json = json_decode(file_get_contents('php://input'), true);
    $token = isset($json['token']) ? $json['token'] : null;
    $server_id = isset($json['server_id']) ? $json['server_id'] : null;
    $url = isset($json['url']) ? $json['url'] : null;

    // 检查参数完整性
    if (!$token || !$server_id || !$url) {
        http_response_code(400);
        die(json_encode(array('code' => 1002, 'msg' => 'Missing required parameters.')));
    }

    // 检查 token 是否有效
    if ($token !== $user_token) {
        http_response_code(400);
        die(json_encode(array('code' => 1002, 'msg' => 'Invalid token.')));
    }

    // 更新服务器信息
    $redis->setEx("jump_$server_id", 1200, $url);

    // 返回成功消息
    header('Content-Type: application/json');
    echo json_encode(array('code' => 0, 'msg' => 'ok'));
}

// 定义 jump 路由
else if ($_SERVER['REQUEST_METHOD'] === 'GET' && preg_match('/^\/(.+)$/', $_SERVER['REQUEST_URI'], $matches)) {
    // 检查请求速率
    $limiter->limit('/<path:url>', 40);

    // 获取客户端请求的 URL
    $url = $matches[1];

    // 从 Redis 中读取数据
    for ($i = 1; $i <= 5; ++$i) {
        if ($redis->exists("jump_$i")) {
            $orig_url = $redis->get("jump_$i");
            break;
        }
    }

    // 如果未找到数据，则使用默认的原始 URL
    if (!isset($orig_url)) {
        $orig_url = $mainurl;
    }

    // 拼接 URL 并重定向客户端
    header('Location: ' . ($orig_url . urlencode($url)));
}