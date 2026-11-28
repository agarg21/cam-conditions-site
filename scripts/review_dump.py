#!/usr/bin/env python3
"""Owner review page: gather every model reading for one review set (bake-off v1.1 Opus/Sonnet/Haiku and the
human-check re-test v2/v3) into one JSON file, encrypted for the owner's chat session (public key ops/keys/review.pub.pem).
The plaintext never touches the repo; only review/<set>/models.enc + models.key.enc are committed.
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from review_export import ROOT, REPO, LABELS

def main(set_name):
    from huggingface_hub import hf_hub_download
    tok = os.environ["HF_TOKEN"]
    out = os.path.join(ROOT, "review", set_name)
    items = json.load(open(os.path.join(out, "items.json")))
    v1 = {}
    for l in open(hf_hub_download(REPO, LABELS, repo_type="dataset", token=tok)):
        if l.strip():
            r = json.loads(l); v1[r["path"]] = {m: x.get("reading") for m, x in r["models"].items()}
    h = {}
    for l in open(hf_hub_download(REPO, f"labels/humancheck/{set_name}-sonnet-v2v3.jsonl", repo_type="dataset", token=tok)):
        if l.strip():
            r = json.loads(l); h[r["id"]] = {"v2": r["v2"].get("reading"), "v3": r["v3"].get("reading")}
    try:
        for l in open(hf_hub_download(REPO, f"labels/humancheck/{set_name}-sonnet-v4.jsonl", repo_type="dataset", token=tok)):
            if l.strip():
                r = json.loads(l); h.setdefault(r["id"], {})["v4"] = r["v4"].get("reading")
    except Exception as e:
        print("no v4 file:", e)
    data = {it["id"]: {"v1": v1.get(it["path"], {}), **h.get(it["id"], {})} for it in items}
    d = tempfile.mkdtemp()
    plain, key = os.path.join(d, "p.json"), os.path.join(d, "k")
    json.dump(data, open(plain, "w"))
    open(key, "wb").write(os.urandom(32).hex().encode())
    pub = os.path.join(ROOT, "ops", "keys", "review.pub.pem")
    subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-salt", "-in", plain, "-out", os.path.join(out, "models.enc"), "-pass", f"file:{key}"], check=True)
    subprocess.run(["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", pub, "-pkeyopt", "rsa_padding_mode:oaep", "-in", key, "-out", os.path.join(out, "models.key.enc")], check=True)
    print("encrypted", len(data), "items")

if __name__ == "__main__":
    main(sys.argv[1])
