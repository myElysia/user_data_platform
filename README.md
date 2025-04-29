/user_data_platform/
├── main.py              # 主入口
├── app/
│   ├── models.py            # Tortoise模型
│   ├── schemas.py           # Pydantic模型
│   ├── services.py              # 数据库操作
│   ├── auth.py              # 认证相关
│   ├── oauth2.py            # OAuth2相关
│   ├── grpc_services/       # gRPC服务
│   ├── api/
│   │   ├── endpoints/   # API端点
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── third_party.py
│   │   ├── grpc/        # gRPC接口
├── config.py            # 配置文件
├── migrations/              # 数据库迁移
├── static/                  # 静态文件
├── requirements.txt
└── Dockerfile
