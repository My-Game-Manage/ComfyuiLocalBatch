import argparse
import time
import json
import urllib.request
import urllib.parse
import websocket # 要 pip install websocket-client
import uuid
import random
import subprocess
from pathlib import Path

SERVER_ADDRESS = "127.0.0.1:8188"
CLIENT_ID = str(uuid.uuid4())

def queue_prompt(prompt_workflow):
    """ComfyUIのキューにプロンプトを送信する"""
    data = json.dumps({"prompt": prompt_workflow, "client_id": CLIENT_ID}).encode('utf-8')
    req = urllib.request.Request(f"http://{SERVER_ADDRESS}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

def wait_for_completion(ws, prompt_id):
    """WebSocketで指定したprompt_idの生成が完了するのを待機する"""
    while True:
        out = ws.recv()
        if not isinstance(out, str):
            # プレビュー画像などのバイナリデータはスキップ
            continue

        message = json.loads(out)
        msg_type = message.get("type")
        data = message.get("data", {})

        if msg_type == "executing":
            if data.get("node") is None and data.get("prompt_id") in (prompt_id, None):
                break
        elif msg_type == "execution_success":
            if data.get("prompt_id") == prompt_id:
                break

def set_random_seed(workflow_api_json):
    """ワークフロー内のKSamplerノードを探してランダムなseed値を設定する"""
    new_seed = random.randint(1, 2**32 - 1)
    for node_id, node_data in workflow_api_json.items():
        if node_data.get("class_type") in ["KSampler", "KSamplerAdvanced"]:
            if "seed" in node_data.get("inputs", {}):
                node_data["inputs"]["seed"] = new_seed
                print(f"  -> Node [{node_id}] の seed を {new_seed} に設定しました")

def notify_linux(title: str, message: str):
    """Lubuntu（Linux）向けにデスクトップ通知とターミナル出力を行う"""
    print(f"\a[{title}] {message}")  # \a で端末ベル（環境によりビープ音）
    try:
        subprocess.run(
            ["notify-send", title, message],
            check=False,
        )
    except FileNotFoundError:
        # notify-send が未導入の場合は標準出力のみにフォールバック
        pass

def run_sequential_generation(workflow_api_json, total_images=8, delay_sec=1.0):
    """指定した枚数分、ウェイトを挟みながら1枚ずつ実行する"""
    ws = websocket.WebSocket()
    ws.connect(f"ws://{SERVER_ADDRESS}/ws?clientId={CLIENT_ID}")
    
    for i in range(total_images):
        print(f"[{i+1}/{total_images}] 生成を開始します...")
        
        # 1枚ごとにランダムなシード値をセット
        set_random_seed(workflow_api_json)

        # キューに投入
        prompt_response = queue_prompt(workflow_api_json)
        prompt_id = prompt_response['prompt_id']
        
        # 完了を待つ
        wait_for_completion(ws, prompt_id)
        print(f"-> 1枚の生成が完了しました。{delay_sec}秒間待機します...")
        
        # 指定した秒数（1秒など）待機（GPUの負荷やVRAM解放を待つ）
        time.sleep(delay_sec)
        
    ws.close()
    print("すべての処理が完了しました！")
    summary = f"全{total_images}枚の画像生成が完了しました！"
    notify_linux("ComfyUI バッチ完了", summary)

def parse_args():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description="ComfyUI APIを使って画像を1枚ずつ順次生成します。"
    )
    parser.add_argument(
        "-n", "--num", "--count",
        type=int,
        default=8,
        help="生成する枚数（デフォルト: 8）",
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=1.0,
        help="1枚ごとの待機秒数（デフォルト: 1.0）",
    )
    parser.add_argument(
        "-w", "--workflow",
        type=Path,
        default=Path("out1.json"),
        help="API形式ワークフローJSONのパス（~/... 指定可、デフォルト: out1.json）",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    # args.workflow は Path オブジェクト（例: -w home なら Path("home")）
    raw_arg = str(args.workflow).strip()

    if args.num <= 0:
        raise ValueError("枚数（--num）には1以上の整数を指定してください。")

    if raw_arg.lower() == "home":
        # "home" が指定されたときの専用処理
        print("home モードの処理を実行します")

        # 現在のユーザーのホームディレクトリ（例: /home/username）を自動取得
        home_dir = Path.home()
        base_dir = home_dir / "Works"
        json_path = base_dir / "out1.json"
    else:
        # 通常のファイルパス指定として扱う場合
        json_path = args.workflow.expanduser()    
    
    # 対象のJSONファイルを読み込み
    with open(json_path, "r", encoding="utf-8") as f:
        workflow_data = json.load(f)
        
    # 10枚生成・1秒待機で実行
    run_sequential_generation(
        workflow_data,
        total_images=args.num,
        delay_sec=args.delay,
    )
