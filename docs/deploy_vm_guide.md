# ComfyUI 웹 → VMware VM Docker 배포 가이드

```
[브라우저] ──► [VMware VM: Docker 컨테이너 (Flask)] ──► [GPU 서버: ComfyUI <GPU 서버 IP>:8188]
                 :5000 → 코드가 이미지 안에 들어있음
                 :5001 → 코드는 VM 폴더를 -v 로 연결 (서버/코드 분리)
```

---

## 0. 옮겨야 하는 파일

VM의 `~/comfyui` 폴더가 아래처럼 되어 있으면 됩니다.

```
~/comfyui/
├── app.py                 # Flask 웹 서버 코드
├── requirements.txt       # 필요한 패키지 (flask, requests)
├── Dockerfile             # 컨테이너 이미지 만드는 설정
├── templates/
│   └── image.html         # 웹 화면 (디자인)
└── static/
    └── test.json          # ComfyUI 워크플로 (API 형식으로 저장한 것)
```

| 파일 | 꼭 필요? | 설명 |
|---|---|---|
| app.py | ✅ | 웹 서버 본체 |
| requirements.txt | ✅ | `docker build` 때 설치할 패키지 |
| Dockerfile | ✅ | 이미지 빌드 설정 |
| templates/image.html | ✅ | 폴더 이름 `templates` 그대로 (Flask 규칙) |
| static/test.json | ✅ | 폴더 이름 `static` 그대로 |
| deploy_vm.sh | ❌ | 위 파일들을 VM으로 **옮기는 도구**일 뿐, 실행엔 필요 없음 |
| `__pycache__/` | ❌ | 자동 생성 파일, 옮기지 않음 |

---

## 1. 사전 준비 (한 번만)

**GPU 서버** – ComfyUI를 외부 접속 허용으로 실행

```bash
python main.py --listen 0.0.0.0 --port 8188
```

**VM (PuTTY)** – 연결 확인 + 포트 열기

```bash
systemd-detect-virt                              # vmware 나오면 VM 맞음
curl http://<GPU 서버 IP>:8188/system_stats     # JSON 나오면 GPU 서버 연결 OK
sudo ufw allow 5000
sudo ufw allow 5001
```

---

## 2. 파일을 VM으로 옮기기

### 방법 A: deploy_vm.sh 붙여넣기 (이번에 쓴 방법)

`deploy_vm.sh` 안에 위 5개 파일이 압축돼 들어있습니다.
(`deploy_vm.sh` 는 이 저장소에 포함하지 않았다. 코드를 고쳤다면 스크립트도 다시 만들어야 한다.)

```bash
nano ~/deploy.sh
#  - 기존 내용 있으면 Ctrl+K 반복으로 지우기
#  - VS Code에서 deploy_vm.sh 전체 복사(Ctrl+A, Ctrl+C)
#  - PuTTY 창에 마우스 오른쪽 클릭 = 붙여넣기
#  - Ctrl+O → Enter → Ctrl+X 로 저장
bash ~/deploy.sh
```

이 스크립트가 하는 일: Docker 설치(없을 때) → `~/comfyui` 에 파일 풀기 → 이미지 빌드 → 5000번 컨테이너 실행

### 방법 B: 파일이 Windows에 있을 때 (WinSCP / pscp)

- **WinSCP**: VM IP, VM 사용자 계정으로 접속 → `comfyui` 폴더를 `/home/<사용자>/` 로 드래그
- **pscp** (PuTTY 설치하면 같이 있음, Windows 명령 프롬프트에서):

```bat
pscp -r C:\경로\comfyui <사용자>@<VM IP>:/home/<사용자>/
```

방법 B로 옮긴 뒤에는 아래 3번을 직접 실행합니다.

---

## 3. 이미지 빌드 + 5000번 실행 (코드가 이미지 안에 들어감)

```bash
sudo apt install -y docker.io            # Docker 없을 때만
cd ~/comfyui
sudo docker build -t comfy-web .
sudo docker rm -f comfy-web 2>/dev/null
sudo docker run -d --name comfy-web --restart unless-stopped \
  -p 5000:5000 \
  -e COMFY_URL=http://<GPU 서버 IP>:8188 \
  comfy-web
```

→ 브라우저: `http://<VM IP>:5000`  (VM IP 확인: `hostname -I`)

---

## 4. 5001번 실행 (`-v` 로 서버/코드 분리)

```bash
sudo docker rm -f comfy-web-5001 2>/dev/null
sudo docker run -d --name comfy-web-5001 --restart unless-stopped \
  -p 5001:5000 \
  -v ~/comfyui:/app \
  -e COMFY_URL=http://<GPU 서버 IP>:8188 \
  comfy-web
```

→ 브라우저: `http://<VM IP>:5001`

| 옵션 | 뜻 |
|---|---|
| `-p 5001:5000` | VM 5001 포트 → 컨테이너 안 5000 포트 |
| `-v ~/comfyui:/app` | VM 폴더를 컨테이너 `/app` 에 연결 (이미지 속 코드 대신 VM 폴더 코드 실행) |
| `-e COMFY_URL=...` | GPU 서버 주소 전달 |
| `comfy-web` | 3번에서 만든 이미지 (Python + Flask 실행 환경으로만 사용) |

---

## 5. 코드 수정할 때

| | 5000번 (이미지 방식) | 5001번 (`-v` 방식) |
|---|---|---|
| 수정 위치 | VM `~/comfyui` | VM `~/comfyui` |
| 반영 방법 | `docker build` 다시 + 컨테이너 다시 실행 (3번) | `sudo docker restart comfy-web-5001` 만 |

```bash
nano ~/comfyui/templates/image.html
sudo docker restart comfy-web-5001
```

> `requirements.txt` 에 패키지를 추가했다면 5001번도 **3번(이미지 빌드)부터** 다시 해야 합니다.

---

## 6. 자주 쓰는 명령

```bash
sudo docker ps                         # 실행 중인 컨테이너
sudo docker logs -f comfy-web-5001     # 로그 보기 (Ctrl+C로 나가기)
sudo docker restart comfy-web-5001     # 재시작
sudo docker stop comfy-web-5001        # 멈추기
sudo docker rm -f comfy-web-5001       # 지우기 (VM 폴더 코드는 남음)
```

---

## 7. 이번에 겪은 문제와 해결

| 증상 | 원인 / 해결 |
|---|---|
| `cd: comfyui: No such file or directory` | 파일을 VM으로 안 옮김 → 2번 먼저 |
| `python: command not found` | Ubuntu는 `python3` (Docker 방식이면 신경 안 써도 됨) |
| `ensurepip is not available`, `pip not found` | venv 방식 문제 → Docker 방식으로 해결 |
| 브라우저 접속 안 됨 | `sudo ufw allow 5000` / `5001`, VMware 네트워크가 NAT이면 Bridged로 |
| "GPU 서버에 연결할 수 없습니다" | GPU 서버 ComfyUI가 `--listen 0.0.0.0` 으로 켜져 있는지, `curl` 로 확인 |
| 이미지가 안 나오고 시간 초과 | GPU 서버에서 ComfyUI 로그 확인, `static/test.json` 노드 번호(6, 7, 13) 확인 |
