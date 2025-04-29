import json, os, urllib.request, urllib.error, time

# ---------- 環境変数 ----------
API_URL = os.getenv("FASTAPI_URL")            # 例: https://....ngrok-free.app/generate
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", 10))   # sec
MAX_NEW = int(os.getenv("MAX_NEW_TOKENS", 512))
TEMP    = float(os.getenv("TEMPERATURE", 0.7))
TOP_P   = float(os.getenv("TOP_P", 0.9))

# ---------- Lambda ハンドラー ----------
def lambda_handler(event, context):
    try:
        if not API_URL:
            raise RuntimeError("環境変数 FASTAPI_URL が未設定です")

        # 1) フロントから来た JSON を取り出す
        body_json = json.loads(event["body"])
        user_msg  = body_json["message"]
        history   = body_json.get("conversationHistory", [])

        prompt = user_msg

        # 2) FastAPI /generate 用の JSON ペイロード
        payload = {
            "prompt":          prompt,
            "max_new_tokens":  MAX_NEW,
            "do_sample":       True,
            "temperature":     TEMP,
            "top_p":           TOP_P
        }
        data_bytes = json.dumps(payload).encode("utf-8")

        # 3) HTTP POST (urllib.request)
        req = urllib.request.Request(
            API_URL,
            data=data_bytes,
            method="POST",
            headers={"Content-Type": "application/json"}
        )

        t0 = time.time()
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            resp_body = resp.read().decode("utf-8")
            status    = resp.status          # Py3.9+: HTTPResponse.status

        if status != 200:
            raise RuntimeError(f"FastAPI から {status} 応答: {resp_body}")

        resp_json = json.loads(resp_body)
        assistant_text = resp_json.get("generated_text")
        if not assistant_text:
            raise RuntimeError("FastAPI 応答に 'generated_text' がありません")

        t1 = time.time()

        # 4) 必要なら履歴を更新して返す
        new_history = history + [
            {"role": "user",      "content": user_msg},
            {"role": "assistant", "content": assistant_text}
        ]

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
            },
            "body": json.dumps({
                "success": True,
                "latency": round(t1 - t0, 3),
                "response": assistant_text,
                "conversationHistory": new_history
            }, ensure_ascii=False)
        }

    # ---------- エラーハンドリング ----------
    except urllib.error.HTTPError as e:
        err = f"HTTPError {e.code}: {e.read().decode('utf-8')}"
    except urllib.error.URLError as e:
        err = f"URLError: {e.reason}"
    except Exception as e:
        err = str(e)

    return {
        "statusCode": 500,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,POST",
        },
        "body": json.dumps({"success": False, "error": err}, ensure_ascii=False)
    }
