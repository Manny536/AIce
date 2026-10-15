"""JSON CLI: train, query, info, or run the controlled action harness."""

import argparse
import json
import sys

from .harness import demo_harness
from .model import Config, Transformer
from .train import sha256, train


def main(argv=None):
    parser = argparse.ArgumentParser(description="AIce NumPy transformer; experimental")
    commands = parser.add_subparsers(dest="command", required=True)
    training = commands.add_parser("train")
    training.add_argument("--train", required=True)
    training.add_argument("--eval", required=True)
    training.add_argument("--output", required=True)
    training.add_argument("--steps", type=int, default=600)
    training.add_argument("--batch-size", type=int, default=4)
    training.add_argument("--context", type=int, default=64)
    training.add_argument("--width", type=int, default=32)
    training.add_argument("--heads", type=int, default=4)
    training.add_argument("--layers", type=int, default=2)
    training.add_argument("--seed", type=int, default=7)
    training.add_argument("--learning-rate", type=float, default=0.003)
    for name in ("query", "harness", "info"):
        command = commands.add_parser(name)
        command.add_argument("--checkpoint", required=True)
        if name != "info":
            command.add_argument("--prompt", required=True)
        if name == "query":
            command.add_argument("--max-new-tokens", type=int, default=80)
            command.add_argument("--temperature", type=float, default=0.7)
            command.add_argument("--seed", type=int, default=7)
        if name == "harness":
            command.add_argument("--action", help="Optional exact action from the trusted demo catalog")
    args = parser.parse_args(argv)
    if args.command == "train":
        _, receipt = train(args.train, args.eval, args.output,
                           config=Config(args.context, args.width, args.heads, args.layers, args.seed),
                           steps=args.steps, batch_size=args.batch_size, learning_rate=args.learning_rate,
                           progress=lambda item: print(json.dumps(item), file=sys.stderr))
        print(json.dumps(receipt))
        return
    model = Transformer.load(args.checkpoint)
    identity = {"model": "AIce-Tiny-v0", "checkpoint_sha256": sha256(args.checkpoint),
                "parameters": model.parameter_count, "status": "EXPERIMENTAL; efficacy OPEN"}
    if args.command == "info":
        result = identity
    elif args.command == "query":
        result = {**identity, "kind": "ungated_text",
                  "completion": model.generate(args.prompt, max_new_tokens=args.max_new_tokens,
                                               temperature=args.temperature, seed=args.seed)}
    else:
        harness, state, handlers = demo_harness(model)
        receipt = harness.run(args.prompt, "query", state, handlers, requested_action=args.action)
        result = {**identity, "kind": "structured_action_demo", **receipt.to_dict()}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
