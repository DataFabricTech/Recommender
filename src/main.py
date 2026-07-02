from fastapi import APIRouter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Recommender.controller import contorller
from StandardMapping.controller import controller as standard_mapping_controller
from Lib.ConfigHandler import *
from Lib.LogHandler import *

conf = ConfigHandler()
log = LogHandler(code_path=os.path.abspath(__file__), log_filename='Recommender',
                 logkeepdate=conf.LOG_KEEPDATE_LIMIT, print_flag=True)
log.setLoglevel(conf.LOG_LEVEL)

_is_local = conf.loadEnv() == "local"
app = FastAPI(
    title=conf.RECOMMENDER_API_PROJECTNAME,
    openapi_url="/openapi.json" if _is_local else None,
    docs_url="/docs" if _is_local else None,
    redoc_url="/redoc" if _is_local else None,
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)
app.add_middleware(CORSMiddleware, allow_origins=[
    "*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],)

api_router = APIRouter()
api_router.include_router(contorller.router, prefix="/recommender")
# 표준화매핑은 별도 컨테이너 대신 recommender 서비스에 통합 (관리포인트 최소화)
api_router.include_router(standard_mapping_controller.router, prefix="/standard-mapping")
app.include_router(api_router, prefix=conf.RECOMMENDER_API_PREFIXURI)


if __name__ == "__main__":
    import uvicorn

    log.info("recommender app start")
    uvicorn.run("main:app", host='0.0.0.0', port=int(
        conf.RECOMMENDER_API_PORT), reload=True)
