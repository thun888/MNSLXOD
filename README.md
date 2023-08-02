**M**ulti-**N**ode **S**ervice **L**ink **X** **O**ne**D**rive

基于OneDrive的多节点服务链

------

通过该项目，你可以将可以把一些不稳定的服务利用起来，依靠OneDrive的文件存储，实现一个高速的高可用性图床

详细教程：[点击打开](https://blog.hzchu.top/2023/photoononedrive/)

快速版：

使用py均需**安装依赖**：

```bash
pip3 install flask flask_limiter hypercorn
```

**jump**:下载jump文件夹中的index.php或main.py，修改代码中的配置

使用php需配置伪静态：

```nginx
location / {
    try_files $uri $uri/ /index.php?$args;
}
```

**node**:下载jump文件夹中的main.py和data.db，修改代码中的配置并运行即可