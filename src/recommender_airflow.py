from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.hooks.base import BaseHook
from datetime import datetime
import requests

# DAG 기본 설정
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 1, 1),
    'retries': 1,
}
# clustering_training , embeded_training 요청 task 생성.
def get_tasks():
    tasks = [
        # clustering_training 요청 task 생성
        {
            "task_id": "clustering_training",
            "end_point": "/v1/recommender/clusteringTraining"
        },
        # embeded_training 요청 task 생성
        {
            "task_id": "embeded_training",
            "end_point": "/v1/recommender/embeddingTraining"
        }
    ]
    return tasks

def call_api(task_id, end_point):
    try:
        # Airflow에 등록된 connection 활용
        conn = BaseHook.get_connection("metadata_recommend_http")
        base_url = f"http://{conn.host}:{conn.port}"
        # base_url = f"http://localhost:8888"
        url = f"{base_url}/{end_point}"
        response = requests.get(url)
        response.raise_for_status()
        print(f"응답 상태 코드: {response.status_code}")
        print(f"응답 내용: {response.text}")

        payload = response.json()
        service_status = int(payload.get("status_code", response.status_code))
        if service_status >= 400:
            message = payload.get("result", {}).get("message", response.text)
            raise RuntimeError(
                f"[{task_id}] Recommender service failed "
                f"with status_code={service_status}: {message}"
            )
    except requests.exceptions.RequestException as e:
        print(f"[{task_id}] 요청 실패: {e}")
        raise e
        

# DAG 정의
with DAG(
    dag_id='recommender_training',
    default_args=default_args,
    schedule_interval='0 0 * * *',  # 매일 00시반복
    catchup=False,
    tags=["bash", "recommend"]
) as dag:
    tasks = get_tasks()
    
    # 동적으로 task 생성.
    for task in tasks:
        PythonOperator(
            task_id = task["task_id"],
            python_callable=call_api,
            op_kwargs={
                "task_id": task["task_id"],
                "end_point": task["end_point"]
            }
        )
        
   
