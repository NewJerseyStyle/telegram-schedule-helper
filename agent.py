# def chat_flow_interaction
# def get_plan_by_conversation
# def get_user_state_by_history

from starlette.requests import Request
from typing import Dict

from ray import serve

# https://github.com/ztxz16/fastllm
from fastllm_pytools import llm

# 1: Define a Ray Serve application.
@serve.deployment(route_prefix="/", ray_actor_options={"num_cpus": 4})
class MyModelDeployment:
    def __init__(self, path: str = "chatglm2-6b-int4.flm"):
        # Initialize model state: could be very large neural net weights.
        self._model = llm.model(path); # 导入fastllm模型

    async def __call__(self, request: Request) -> Dict:
        input_json = await request.json()
        if "history" not in input_json:
            input_json["history"] = []
        # history = [(user_query, ai_respond)]
        _msg = self._model.response(input_json["text"],
                                    history=input_json["history"],
                                    top_p = 0.8,
                                    top_k = 1,
                                    temperature = 0.2)
        return {"result": _msg}


# app = MyModelDeployment.bind(path="/workspace/chatglm2-6b-fp16.flm")
app = MyModelDeployment.bind(path="/workspace/chatglm2-6b-int4.flm")

# 2: Deploy the application locally.
serve.run(app)
