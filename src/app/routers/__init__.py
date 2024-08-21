from .training_service import router as training_router
from .recommend_service import router as inference_router
from .check import router as check_router

routers = [
    check_router,
    training_router,
    inference_router
]
