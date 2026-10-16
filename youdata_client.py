# -*- coding: utf-8 -*-
"""网易有数 YouData API 客户端。
tokenKey（长期） -> genToken 换短期 token（默认30天有效期，本地缓存复用）。
"""
import json
import time
import urllib.request
import urllib.error
import os

BASE_URL = "https://youdata.yx.netease.com"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
TOKEN_CACHE_PATH = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"), ".token_cache.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _post_json(path, payload, timeout=60):
    url = BASE_URL + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path, params=None, timeout=60):
    url = BASE_URL + path
    if params:
        from urllib.parse import urlencode
        url += "?" + urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_token(force=False):
    """用 tokenKey 换鉴权 token，缓存到本地，默认过期前 1 小时重新生成。"""
    cfg = load_config()
    os.makedirs(os.path.dirname(TOKEN_CACHE_PATH), exist_ok=True)
    if not force and os.path.exists(TOKEN_CACHE_PATH):
        with open(TOKEN_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        if cache.get("token") and cache.get("created", 0) + cache.get("ttl", 86400) - 3600 > time.time():
            return cache["token"]
    # tokenKey 优先取环境变量 BI_TOKEN_KEY（云端/CI 用，避免把密钥写进仓库）
    key = os.environ.get("BI_TOKEN_KEY") or cfg.get("token_key")
    if not key:
        raise RuntimeError("缺少 BI tokenKey：请在 config.json 的 token_key 或环境变量 BI_TOKEN_KEY 中提供")
    r = _post_json("/api/dash/util/genToken", {"tokenType": "tokenKey", "key": key})
    if r.get("code") != 200:
        raise RuntimeError("genToken 失败: %s" % r)
    token = r["result"]
    with open(TOKEN_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump({"token": token, "created": time.time(), "ttl": 86400 * 30}, f)
    return token


def api_post(path, payload, use_token=True, timeout=60):
    if use_token:
        payload = dict(payload, token=get_token())
    return _post_json(path, payload, timeout=timeout)


def api_get(path, params=None, use_token=True, timeout=60):
    if use_token:
        params = dict(params or {}, token=get_token())
    return _get(path, params, timeout=timeout)


def download(url, dest_path):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=300) as resp, open(dest_path, "wb") as f:
        f.write(resp.read())


if __name__ == "__main__":
    print("token =", get_token())
