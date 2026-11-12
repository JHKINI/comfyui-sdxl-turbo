# ComfyUI 웹 → 내 VMware VM Docker 배포 가이드

> 이 문서는 최종 구조(Flux2 버전) 기준으로 정리한 것이다.
> 문서에서 말하는 `app.py` 는 이 저장소의 [`app_flux2.py`](../app_flux2.py) 이고, 저장소의 `app.py` 는 그 전 단계인 SDXL Turbo 버전이다.
> IP 주소와 계정 이름은 `<내 VM IP>`, `<교수님 PC IP>`, `<사용자>` 로 바꿔 적었다.

## 전체 구조 (최종, 동작 확인됨)

```
 내 브라우저
     │  http://<내 VM IP>:5000  또는  :5001
     ▼
 내 VMware VM (<내 VM IP>) ── Docker 컨테이너 (Flask 웹, app.py)
     │  COMFY_URL = http://<교수님 PC IP>:8188
     ▼
 교수님 PC (<교수님 PC IP>) ── ComfyUI + Flux2 모델 (그림 생성)
```

| 주소 | 정체 | 어디에 쓰나 |
|---|---|---|
| `<내 VM IP>` | **내 VMware VM** | 브라우저에 입력 (`:5000`, `:5001`) / PuTTY 접속 |
| `<교수님 PC IP>` | **교수님 PC** (모델 있음) | `COMFY_URL` — 웹이 요청을 보내는 곳 |
| `172.17.0.x` | Docker 내부 주소 | 사용 안 함 |

- 나는 모델이 없음 → 그림은 교수님 PC가 그림
- 내 VM은 **웹 화면 + 요청 전달**만 담당
- 브라우저에 `<교수님 PC IP>:5000` 을 넣으면 안 됨 (교수님 PC엔 웹이 없음)

| 컨테이너 | 포트 | 방식 |
|---|---|---|
| `comfy-web` | 5000 | 코드가 **이미지 안에** 들어있음 (수정 시 재빌드) |
| `comfy-web-5001` | 5001 | 코드는 **VM 폴더를 `-v` 로 연결** (서버/코드 분리, 수정 시 restart만) |

---

## 0. 파일 구성

내 PC(Windows): `D:\경로\comfyui`  →  VM: `~/comfyui`

```
comfyui/
├── app.py                 # Flask 웹 서버 (요청을 교수님 PC로 전달) - 저장소에서는 app_flux2.py
├── requirements.txt       # flask, requests
├── Dockerfile             # 컨테이너 이미지 설정
├── templates/
│   └── image.html         # 웹 화면 디자인
├── static/
│   ├── flux2.json         # ComfyUI 워크플로 (현재 사용, Flux2 Klein)
│   └── test.json          # 예전 SDXL Turbo 워크플로 (안 씀)
├── deploy_vm.sh           # 위 파일들을 VM으로 옮기는 도구 (실행엔 불필요, 저장소에는 포함하지 않음)
└── VM_배포가이드.md       # 이 문서 (저장소에서는 docs/deploy_vm_guide.md)
```

---

## 1. 코드에서 바꾼 것

### app.py

| 항목 | 내용 |
|---|---|
| `COMFY_URL` | 기본값 `http://<교수님 PC IP>:8188`, `docker run -e COMFY_URL=...` 로 덮어쓰기 가능 |
| `WORKFLOW_PATH` | `static/flux2.json` |
| 노드 번호 | 아래 3줄만 템플릿에 맞춰 수정 |
| `/view` 경로 | 이미지를 VM 이 대신 받아서 보여줌 → 브라우저는 VM 만 접속하면 됨 |
| 대기 시간 | 600초 (교수님 PC를 여러 명이 같이 써서 대기열이 길 수 있음) |
| 오류 표시 | 연결 실패/시간 초과를 화면에 빨간 박스로 표시 |

```python
POS_NODE  = ("76",    "value")       # 프롬프트 노드
NEG_NODE  = ("75:67", "text")        # Negative 프롬프트
SEED_NODE = ("75:73", "noise_seed")  # 시드 (매번 랜덤)
```

> 템플릿(JSON)이 바뀌면: ComfyUI에서 **API 형식으로 저장** → `static/` 에 넣기 → 위 3줄 번호 맞추기

### Dockerfile

`python:3.12-slim` + flask/requests 설치 + 코드 복사, `python app.py` 로 실행 (포트 5000)

---

## 2. VM 준비 (한 번만, PuTTY)

```bash
hostname -I                                       # 내 VM IP 확인 → <내 VM IP>
curl -s -m 5 http://<교수님 PC IP>:8188/system_stats | head -c 200; echo
                                                  # JSON 나오면 교수님 PC 연결 OK
sudo ufw allow 5000
sudo ufw allow 5001
```

---

## 3. 파일을 VM으로 옮기기

### 방법 A: deploy_vm.sh 붙여넣기 (직접 해 본 방법 1)

`deploy_vm.sh` 안에 파일들이 압축돼 들어있음.
**코드를 고친 뒤엔 `deploy_vm.sh` 도 다시 만들어야 한다** (안 그러면 옛날 코드가 올라감)

```bash
nano ~/deploy.sh
#  - Ctrl+K 반복 → 기존 내용 전부 지우기
#  - VS Code에서 deploy_vm.sh 전체 복사 (Ctrl+A, Ctrl+C)
#  - PuTTY 창에 마우스 오른쪽 클릭 = 붙여넣기
#  - Ctrl+O → Enter → Ctrl+X
bash ~/deploy.sh
```

하는 일: Docker 설치(없을 때) → `~/comfyui` 에 파일 풀기 → 이미지 빌드 → **5000번 컨테이너 실행**

### 방법 B: scp (직접 해 본 방법 2)

Windows에 기본으로 들어 있어서 설치가 필요 없다. PuTTY로 접속이 되면 이 방법도 된다.
VM(PuTTY 창)이 아니라 **내 PC의 PowerShell** 에서 실행한다. 비밀번호는 PuTTY 비밀번호와 같다.

```powershell
scp -r D:\경로\comfyui <사용자>@<내 VM IP>:~/
```

파일 하나만 바꿨을 때:

```powershell
scp D:\경로\comfyui\app.py <사용자>@<내 VM IP>:~/comfyui/
```

### 방법 C: WinSCP (참고, 해 보지는 않음)

- WinSCP 설치 → 새 사이트: 프로토콜 `SFTP`, 호스트 `<내 VM IP>`, 포트 `22`, 사용자 `<사용자>`
- 왼쪽(내 PC) `D:\경로\comfyui` → 오른쪽(VM) `/home/<사용자>/` 로 드래그

### 방법 D: GitHub (참고, 해 보지는 않음)

```bash
# 내 PC에서 GitHub 저장소에 push 한 뒤, VM에서:
git clone https://github.com/<내아이디>/<저장소>.git ~/comfyui   # 처음
cd ~/comfyui && git pull                                         # 다음부터
```

**방법 B/C/D 후엔 deploy.sh 가 해주던 일을 직접 실행:**

```bash
cd ~/comfyui
sudo docker build -t comfy-web .            # 5000번용 (코드가 이미지에 들어감)
sudo docker rm -f comfy-web
sudo docker run -d --name comfy-web --restart unless-stopped \
  -p 5000:5000 -e COMFY_URL=http://<교수님 PC IP>:8188 comfy-web
sudo docker restart comfy-web-5001          # 5001번은 재시작만
```

5001번(`-v`)만 쓴다면 파일을 옮긴 뒤 `sudo docker restart comfy-web-5001` 한 줄이면 끝난다. 파일을 옮겨서 고치기에는 이 방식이 제일 편했다.

---

## 4. 5000번: 이미지 빌드 + 실행

(방법 A를 썼으면 이미 됨)

```bash
cd ~/comfyui
sudo docker build -t comfy-web .
sudo docker rm -f comfy-web 2>/dev/null
sudo docker run -d --name comfy-web --restart unless-stopped \
  -p 5000:5000 \
  -e COMFY_URL=http://<교수님 PC IP>:8188 \
  comfy-web
```

→ 브라우저: **http://<내 VM IP>:5000**

---

## 5. 5001번: `-v` 로 서버/코드 분리

```bash
sudo docker rm -f comfy-web-5001 2>/dev/null
sudo docker run -d --name comfy-web-5001 --restart unless-stopped \
  -p 5001:5000 \
  -v ~/comfyui:/app \
  -e COMFY_URL=http://<교수님 PC IP>:8188 \
  comfy-web
```

→ 브라우저: **http://<내 VM IP>:5001**

| 옵션 | 뜻 |
|---|---|
| `-p 5001:5000` | VM 5001 포트 → 컨테이너 안 5000 포트 |
| `-v ~/comfyui:/app` | VM 폴더를 컨테이너 `/app` 에 연결 (VM 폴더 코드가 실행됨) |
| `-e COMFY_URL=...` | 요청 보낼 곳 = 교수님 PC |
| `comfy-web` | 4번에서 만든 이미지 (Python + Flask 실행 환경으로만 사용) |

---

## 6. 잘 됐는지 확인

```bash
sudo docker ps                                   # comfy-web, comfy-web-5001 둘 다 Up
curl -s localhost:5000 | grep 'class="server"'   # GPU http://<교수님 PC IP>:8188 나오면 OK
curl -s localhost:5001 | grep 'class="server"'
```

웹 화면 오른쪽 위에 `GPU http://<교수님 PC IP>:8188` 표시 → 교수님 PC로 요청 중

---

## 7. 바꾸고 싶을 때

| 바꿀 것 | 5000번 (이미지) | 5001번 (`-v`) |
|---|---|---|
| 코드/디자인/JSON | 파일 올리기 → 4번 (재빌드) | 파일 올리기 → `sudo docker restart comfy-web-5001` |
| 교수님 PC IP | `docker rm -f` 후 `-e COMFY_URL=새IP` 로 다시 run | 동일 (restart 로는 안 바뀜) |
| requirements.txt | 4번 재빌드 | 4번 재빌드 후 5번 다시 run |

---

## 8. 자주 쓰는 명령

```bash
sudo docker ps -a                      # 컨테이너 상태 (Up / Exited)
sudo docker logs -f comfy-web-5001     # 로그 (Ctrl+C로 나가기)
sudo docker restart comfy-web-5001     # 재시작
sudo docker stop comfy-web-5001        # 멈추기
sudo docker rm -f comfy-web-5001       # 지우기 (VM 폴더 코드는 남음)
```

---

## 9. 이번에 겪은 문제와 해결

| 증상 | 원인 / 해결 |
|---|---|
| `SyntaxError` (app.py 21줄) | `{"noise_seed"}` → `["noise_seed"]`, `randit` → `randint`, `2*32` → `2**32` |
| `cd: comfyui: No such file or directory` | VM에 파일을 안 옮김 → 3번 먼저 |
| `python: command not found`, `pip`/`venv` 오류 | Ubuntu 기본 환경 문제 → Docker 방식으로 해결 |
| 템플릿을 Flux2로 바꾼 뒤 동작 안 함 | 노드 번호가 달라짐 → `POS_NODE`/`NEG_NODE`/`SEED_NODE` 수정 |
| 교수님 PC IP 변경 후에도 예전 IP로 요청 | 컨테이너는 실행 때 받은 `-e` 값 유지 → `rm -f` 후 새 IP로 다시 run |
| VM에 flux2.json 없음 | 예전 deploy.sh 를 실행했음 → 새 deploy_vm.sh 로 교체 후 재실행 |
| `<교수님 PC IP>:5000` 안 열림 | 그건 교수님 PC 주소 → 브라우저엔 **내 VM IP `<내 VM IP>`** |
| 로그에 `GET /` 줄이 없음 | 브라우저 요청이 VM까지 안 온 것 → 주소/포트/방화벽 확인 |
| 생성이 오래 걸림 / 시간 초과 | 교수님 PC 대기열이 김 (여러 명 사용) → 대기 시간 600초로 늘림 |
| `hostname -I` 에 교수님 PC 주소가 없음 | 정상 — 이 명령은 **내 VM 주소만** 보여줌 |
