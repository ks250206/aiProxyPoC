import os
import sys
import subprocess
from dotenv import load_dotenv

def main():
    # .envファイルから環境変数をロード
    load_dotenv()
    
    # Ollamaのエンドポイントが設定されているか確認
    if not os.getenv("OLLAMA_API_BASE"):
        print("Error: OLLAMA_API_BASE is not set in .env file.", file=sys.stderr)
        sys.exit(1)
        
    port = os.getenv("LITELLM_PORT", "4000")
    print(f"Starting LiteLLM Proxy on port {port}...")
    print(f"Routing to Ollama at: {os.getenv('OLLAMA_API_BASE')}")

    # LiteLLM Proxyを実行するためのコマンド
    # .envからロードした環境変数を引き継いでサブプロセスで実行します
    env = os.environ.copy()
    
    # 仮想環境(venv)の litellm を確実に呼び出すために、まず 'litellm' の直接実行を試み、
    # 失敗した場合は 'uv run litellm' 経由で実行します。
    cmd = ["litellm", "--config", "litellm_config.yaml", "--port", port, "--host", "0.0.0.0"]
    
    try:
        subprocess.run(cmd, env=env, check=True)
    except KeyboardInterrupt:
        print("\nStopping LiteLLM Proxy...")
    except FileNotFoundError:
        # 'litellm' コマンドが直接パスに通っていない場合は 'uv run' を挟む
        uv_cmd = ["uv", "run", "litellm", "--config", "litellm_config.yaml", "--port", port, "--host", "0.0.0.0"]
        try:
            subprocess.run(uv_cmd, env=env, check=True)
        except KeyboardInterrupt:
            print("\nStopping LiteLLM Proxy...")
        except Exception as e:
            print(f"Error starting LiteLLM Proxy via uv: {e}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error starting LiteLLM Proxy: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
