from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import logger
from app.data.database import init_db
from app.api.routes import router as api_router

# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# 配置静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 注册路由
app.include_router(api_router, prefix="/api")

# 首页路由
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 应用启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("应用启动...")
    # 初始化数据库
    init_db()
