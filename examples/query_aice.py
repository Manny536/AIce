"""Persistent JSON-lines interface for a local harness.

Run from a checkout after pip install -e '.[model]'. One JSON request on
stdin produces one JSON result on stdout; the checkpoint loads only once.
"""

import argparse
import json
import sys

from aice_model import Transformer
from aice_model.harness import demo_harness
from aice_model.train import sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()
    model = Transformer.load(args.checkpoint)
    digest = sha256(args.checkpoint)
    harness, state, handlers = demo_harness(model)
    for line in sys.stdin:
        request_id = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            request_id = request.get("id")
            prompt = request["prompt"]
            if not isinstance(prompt, str) or len(prompt.encode("utf-8")) > 16384:
                raise ValueError("prompt must be text up to 16384 UTF-8 bytes")
            mode = request.get("mode", "action")
            if mode == "text":
                limit = request.get("max_new_tokens", 80)
                if type(limit) is not int or not 0 <= limit <= 512:
                    raise ValueError("max_new_tokens must be an integer from 0 to 512")
                result = {"kind": "ungated_text", "completion": model.generate(
                    prompt, max_new_tokens=limit, temperature=request.get("temperature", 0.7),
                    seed=request.get("seed", 7))}
            elif mode == "action":
                if request.get("action") is not None and not isinstance(request["action"], str):
                    raise ValueError("action must be a catalog name")
                result = {"kind": "structured_action_demo", **harness.run(
                    prompt, "query", state, handlers, requested_action=request.get("action")).to_dict()}
            else:
                raise ValueError("mode must be text or action")
        except (ValueError, TypeError, KeyError) as error:
            result = {"outcome": "ERROR", "reason": str(error), "executed_action": None}
        print(json.dumps({"id": request_id, "checkpoint_sha256": digest, **result}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
