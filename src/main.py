from fastapi import APIRouter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Recommender.controller import contorller
from Lib.ConfigHandler import *
from Lib.LogHandler import *

conf = ConfigHandler()
log = LogHandler(code_path=os.path.abspath(__file__), log_filename='Recomender',
                 logkeepdate=conf.LOG_KEEPDATE_LIMIT, print_flag=True)
log.setLoglevel(conf.LOG_LEVEL)

app = FastAPI(title=conf.RECOMMENDER_API_PROJECTNAME, openapi_url=None,
              redoc_url=None, swagger_ui_parameters={"defaultModelsExpandDepth": -1})
app.add_middleware(CORSMiddleware, allow_origins=[
    "*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],)

api_router = APIRouter()
api_router.include_router(contorller.router, prefix="/recommender")
app.include_router(api_router, prefix=conf.RECOMMENDER_API_PREFIXURI)


if __name__ == "__main__":
    import uvicorn

    log.info("recommender app start")
    uvicorn.run("main:app", host='0.0.0.0', port=int(
        conf.RECOMMENDER_API_PORT), reload=True)
