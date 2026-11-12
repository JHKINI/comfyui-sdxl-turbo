# app.py
from flask import Flask, request, render_template, Response, abort
import requests, json, time, os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# GPU 서버(ComfyUI) 주소 — 환경변수 COMFY_URL 로 변경 가능
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
WORKFLOW_PATH = os.environ.get("WORKFLOW_PATH", os.path.join(BASE_DIR, "static", "test.json"))
 
app = Flask(__name__)
 
# ---------- 기능별 함수 ----------
def load_workflow(path: str) -> dict:
    """JSON 워크플로를 파일에서 읽기"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Workflow not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
 
def update_prompts(graph: dict, pos: str, neg: str,
                   pos_node_id: str = "6", neg_node_id: str = "7") -> dict:
    graph["13"]["inputs"]["noise_seed"] = random.randint(0, 2**32 - 1)  # 시드 랜덤화
    graph[pos_node_id]["inputs"]["text"] = pos    
    graph[neg_node_id]["inputs"]["text"] = neg
    return graph
def submit_prompt(graph: dict) -> str:
    #ComfyUI /prompt 에 워크플로 제출 후 prompt_id 반환
    r = requests.post(f"{COMFY_URL}/prompt", json={"prompt": graph}, timeout=10)
    r.raise_for_status()
    return r.json()["prompt_id"]
 
def poll_history(prompt_id: str, timeout_sec: int = 180, interval: float = 1.0) -> dict | None:
    """
    간단 폴링: /history/{prompt_id} 에서 완료 결과를 받을 때까지 대기
    """
    end = time.time() + timeout_sec
    while time.time() < end:
        h = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=10)
        if h.status_code == 200 and h.json():
            return list(h.json().values())[0]  # 해당 prompt의 히스토리 블록
        time.sleep(interval)
    return None
def extract_first_image_url(history_block: dict) -> str:
    """
    히스토리 블록에서 SaveImage 출력의 첫 번째 이미지를 view URL로 구성
    (브라우저가 GPU 서버에 직접 접근하지 않도록 Flask 의 /view 프록시 경로 사용)
    """
    if not history_block:
        return ""
    outputs = history_block.get("outputs", {})
    for node_id, node_out in outputs.items():
        if "images" in node_out and node_out["images"]:
            img = node_out["images"][0]
            fn  = img.get("filename")
            sub = img.get("subfolder", "")
            t   = img.get("type", "output")
            if fn:
                from urllib.parse import urlencode
                return "/view?" + urlencode({"filename": fn, "subfolder": sub, "type": t})
    return ""
# ---------- Flask 라우트 ----------
@app.route("/", methods=["GET", "POST"])
def index():
    pos = request.form.get("pos", "a beautiful landscape with galaxy in a bottle")
    neg = request.form.get("neg", "text, watermark")
    img_url = ""
    error = ""
    elapsed = None

    if request.method == "POST":
        start = time.time()
        try:
            graph = load_workflow(WORKFLOW_PATH)
            graph = update_prompts(graph, pos, neg)  # 필요 시 노드 ID 인자 조정 가능
            prompt_id = submit_prompt(graph)
            history_block = poll_history(prompt_id)
            img_url = extract_first_image_url(history_block)
            if not img_url:
                error = "시간 안에 이미지가 생성되지 않았습니다. GPU 서버 상태를 확인하세요."
        except requests.exceptions.ConnectionError:
            error = f"GPU 서버({COMFY_URL})에 연결할 수 없습니다."
        except Exception as e:
            error = f"오류: {e}"
        elapsed = round(time.time() - start, 1)

    return render_template("image.html", pos=pos, neg=neg, img_url=img_url,
                           error=error, elapsed=elapsed, comfy_url=COMFY_URL)

@app.route("/view")
def view():
    """GPU 서버의 이미지를 VM(Flask)을 거쳐 전달 — 브라우저는 VM 만 접근하면 됨"""
    params = {k: request.args.get(k, "") for k in ("filename", "subfolder", "type")}
    if not params["filename"]:
        abort(400)
    r = requests.get(f"{COMFY_URL}/view", params=params, timeout=30)
    if r.status_code != 200:
        abort(r.status_code)
    return Response(r.content, mimetype=r.headers.get("Content-Type", "image/png"))
 
if __name__ == "__main__":
    # pip install flask requests
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("DEBUG", "0") == "1")
 
 