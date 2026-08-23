# ---- 多阶段构建 ----
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir --user -e ".[dev]"

# ---- 运行阶段 ----
FROM python:3.12-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 复制已安装的包
COPY --from=builder /root/.local /root/.local

# 确保 bin 在 PATH 中
ENV PATH=/root/.local/bin:$PATH

# 复制应用代码
COPY . .

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/healthy').raise_for_status()" || exit 1

# 启动命令
CMD ["python", "main.py", "app", "start", "--host", "0.0.0.0", "--port", "8000"]