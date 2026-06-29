from fastapi import APIRouter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from StandardMapping.controller import controller
from Lib.ConfigHandler import *
from Lib.LogHandler import *

conf = ConfigHandler()
log = LogHandler(code_path=os.path.abspath(__file__), log_filename='StandardMapping',
                 logkeepdate=conf.LOG_KEEPDATE_LIMIT, print_flag=True)
log.setLoglevel(conf.LOG_LEVEL)

_is_local = conf.loadEnv() == "local"
app = FastAPI(
    title=conf.STANDARD_MAPPING_API_PROJECTNAME,
    openapi_url="/openapi.json" if _is_local else None,
    docs_url="/docs" if _is_local else None,
    redoc_url="/redoc" if _is_local else None,
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)
app.add_middleware(CORSMiddleware, allow_origins=[
    "*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],)

api_router = APIRouter()
api_router.include_router(controller.router, prefix="/standard-mapping")
app.include_router(api_router, prefix=conf.STANDARD_MAPPING_API_PREFIXURI)


if __name__ == "__main__":
    import uvicorn

    log.info("standard mapping app start")
    uvicorn.run("main:app", host='0.0.0.0', port=int(
        conf.STANDARD_MAPPING_API_PORT), reload=True)
