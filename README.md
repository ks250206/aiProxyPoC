# aiProxyPoC: LiteLLM + Ollama リバースプロキシ＆キューサーバー

このプロジェクトは、ローカルで動作する **Ollama** の前段に **LiteLLM Proxy** を配置し、APIのOpenAI互換化（リバースプロキシ）と、同時実行数の制限に伴うリクエストキュー（待機列処理）機能を提供するPoC（概念実証）実装です。

## 🌟 主な機能
- **OpenAI互換APIエンドポイント**: OllamaのAPIをOpenAI互換形式に統一し、OpenAI SDK等から直接呼び出せるようにします。
- **リクエストキュー（同時実行制御）**: `max_parallel_requests` 設定を超えた並行リクエストが発生した際、エラーにせずプロキシ側でキュー（待機列）に保持し、処理中のリクエストが終わり次第順次実行します。
- **環境変数の管理**: Ollamaのエンドポイントやプロキシのポートなどの構成情報を `.env` で一元管理します。
- **uvによる高速かつ安定した依存関係管理**: Python 3.12環境をサポートし、迅速なセットアップが可能です。

---

## 🛠️ 必要条件
- **Python 3.12+**
- **uv** (高速なPythonパッケージ・プロジェクトマネージャー)
- **Ollama** (ローカルで実行中であり、使用するモデルがプルされていること)

---

## 🚀 セットアップ

### 1. 依存関係のインストール
`uv` を用いて、仮想環境の作成と必要な依存関係（`litellm[proxy]`, `python-dotenv`）のインストールを自動で行います。
```bash
uv sync
```

### 2. 環境変数の設定
`.env.example` をコピーして `.env` ファイルを作成し、ご自身の環境に合わせて編集します。
```bash
cp .env.example .env
```

`.env` の内容：
```env
# OllamaのAPIエンドポイント
OLLAMA_API_BASE="http://localhost:11434"

# LiteLLM Proxyの起動ポート
LITELLM_PORT=4000
```

### 3. モデルとキューの設定の調整
`litellm_config.yaml` でプロキシが提供するモデルと同時実行数の上限を設定します。

```yaml
model_list:
  - model_name: ollama-qwen               # クライアントから指定するモデル名
    litellm_params:
      model: ollama/qwen3.5:35b              # Ollama側に登録されているモデル名
      api_base: os.environ/OLLAMA_API_BASE
      # 同時実行制限 (この制限を超えたリクエストは自動でキューに入り、順次実行されます)
      max_parallel_requests: 1

litellm_settings:
  # キューで待機する可能性を考慮し、タイムアウト時間を長めに設定 (秒単位)
  request_timeout: 600
```

---

## 🏃 実行方法

プロキシサーバーを起動するには、以下のコマンドを実行します。
```bash
uv run python main.py
```
起動が完了すると、`http://0.0.0.0:4000` でリクエストの受付が始まります。

---

## 🧪 動作検証

### 1. 基本的なAPI呼び出しテスト (curl)
起動したプロキシ経由でチャット補完APIを呼び出せるか検証します。
```bash
curl --location 'http://localhost:4000/v1/chat/completions' \
--header 'Content-Type: application/json' \
--data '{
  "model": "ollama-qwen",
  "messages": [{"role": "user", "content": "Hello! Respond in 3 words."}]
}'
```

### 2. キューイング（同時実行制限）の動作検証
複数の並行リクエストを同時に送信した際、直列化されてキューイングされるかを確認するための検証用Pythonスクリプトを作成します。

#### 検証用スクリプトの作成 (`test_queue.py`)
```python
import asyncio
import time
import httpx

async def send_request(request_id: int):
    url = "http://localhost:4000/v1/chat/completions"
    payload = {
        "model": "ollama-qwen",
        "messages": [{"role": "user", "content": f"Request {request_id}: Write a 50-word story."}]
    }
    
    start_time = time.time()
    print(f"[Request {request_id}] Sent at {start_time:.2f}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        
    end_time = time.time()
    duration = end_time - start_time
    print(f"[Request {request_id}] Completed at {end_time:.2f} (Duration: {duration:.2f}s)")

async def main():
    print("Testing LiteLLM Queueing with max_parallel_requests=1...")
    
    # ほぼ同時に2つのリクエストを送信
    task1 = asyncio.create_task(send_request(1))
    await asyncio.sleep(0.5)  # わずかな遅延を挟んで2つ目を送信
    task2 = asyncio.create_task(send_request(2))
    
    await asyncio.gather(task1, task2)

if __name__ == "__main__":
    asyncio.run(main())
```

#### 検証スクリプトの実行
```bash
uv run python test_queue.py
```

**期待される出力例：**
```text
Testing LiteLLM Queueing with max_parallel_requests=1...
[Request 1] Sent at 1780279085.91
[Request 2] Sent at 1780279086.41
[Request 1] Completed at 1780279089.56 (Duration: 3.65s)
[Request 2] Completed at 1780279093.58 (Duration: 7.17s)
```
*※ リクエスト2は送信後、リクエスト1が完了するまでプロキシのキューで待機（キューイング）されるため、所要時間が累積した結果になっています。*

---

## 💡 運用時のTips

### Redisを用いた高耐久・分散キューイング
デフォルトの動作では、プロキシインスタンスのメモリ上でキューが管理されます。
本番運用で、プロキシサーバーの再起動耐性を持たせたい場合や、複数台のプロキシインスタンス間でキューの状態を共有したい場合は、**Redis** の利用を推奨します。

Redisを立ち上げた状態で、`litellm_config.yaml` に以下を追記するだけで有効化されます。
```yaml
router_settings:
  redis_host: localhost
  redis_port: 6379
```
