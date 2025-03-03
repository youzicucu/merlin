FROM python:3.10-slim

WORKDIR /app

# 安装编译工具
RUN apt-get update && apt-get install -y gcc build-essential

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 确保目录存在
RUN mkdir -p data logs models

# 设置环境变量
ENV PYTHONPATH=/app
ENV PORT=8000

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "main.py"]
