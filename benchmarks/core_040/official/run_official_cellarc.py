"""Schema-only CAEL plugin for the UNMODIFIED official CellARC symbolic harness.

This reproduces a frozen checkpoint on already-viewed public test tasks. It is
not training, a new unseen confirmation, or a modified scoring implementation.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import runpy
import socket
import sys
import time


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cael-root', type=Path, required=True)
    ap.add_argument('--source-manifest', type=Path, required=True)
    ap.add_argument('--upstream', type=Path, required=True)
    ap.add_argument('--upstream-manifest', type=Path, required=True)
    ap.add_argument('--dataset-root', type=Path, required=True)
    ap.add_argument('--dataset-manifest', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--extra-deps', action='append', type=Path, default=[])
    args = ap.parse_args()
    for name in ('cael_root', 'source_manifest', 'upstream', 'upstream_manifest',
                 'dataset_root', 'dataset_manifest', 'output'):
        setattr(args, name, getattr(args, name).resolve())
    assert not args.output.exists(), 'Keep all previous attempts; use a new output directory'
    source = json.loads(args.source_manifest.read_text(encoding='utf-8'))
    for name, expected in source['files'].items():
        assert sha(args.cael_root / name) == expected, name
    upstream = json.loads(args.upstream_manifest.read_text(encoding='utf-8'))
    for repo, entry in upstream['sources'].items():
        for name, expected in entry['files'].items():
            assert sha(args.upstream / repo / name) == expected['sha256'], (repo, name)
    dataset = json.loads(args.dataset_manifest.read_text(encoding='utf-8'))
    for name, expected in dataset['files'].items():
        assert sha(args.dataset_root / name) == expected, name
    args.output.mkdir(parents=True)
    sys.dont_write_bytecode = True
    os.environ.update(CAEL_WEB_SEARCH='0', CAEL_LTM=str(args.output / 'ltm.json'),
                      CAEL_MEMORY_FILE=str(args.output / 'memory.json'),
                      OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                      HF_HUB_OFFLINE='1', HF_DATASETS_OFFLINE='1',
                      PYTHONDONTWRITEBYTECODE='1')
    sys.path[:0] = [str(args.cael_root),
                   str(args.upstream / 'cellarc_baselines'),
                   str(args.upstream / 'cellarc'),
                   *[str(p.resolve()) for p in args.extra_deps]]

    def offline(*unused, **kwargs):
        raise RuntimeError('Official harness reproduction is offline')
    socket.create_connection = socket.getaddrinfo = offline
    socket.socket.connect = socket.socket.connect_ex = offline

    # These imports are from the pinned official source trees. Its package root
    # imports neural baseline definitions; no neural model is instantiated or
    # used by CAEL. Harness-import overhead is not CAEL-only inference memory.
    import baselines.symbolic as symbolic
    from cael_unified import Assistant, __version__

    splits = ['test_interpolation', 'test_extrapolation']
    instances = []
    stream = (args.output / 'predictions.jsonl').open('x', encoding='utf-8')

    class CAELSymbolicAdapter:
        def __init__(self):
            self.split = splits[len(instances)]
            self.model = Assistant(output_root=args.output / self.split / 'outputs')
            self.calls = 0
            instances.append(self)

        def predict(self, episode):
            # The official evaluator retains gold for scoring. The model
            # receives ONLY a new whitelist-built task, never episode itself.
            assert len(episode['train']) == 5
            task = dict(examples=[dict(input=pair['input'], output=pair['output'])
                                  for pair in episode['train']], query=episode['query'])
            assert set(task) == {'examples', 'query'}
            prompt = 'Infer discrete transition: ' + json.dumps(task, separators=(',', ':'))
            started = time.perf_counter()
            reply = error = None
            prediction = []
            try:
                reply = self.model.respond([dict(role='user', content=prompt)],
                                           mode='chat', seed=401107)
            except Exception as exc:
                error = type(exc).__name__ + ': ' + str(exc)
            try:
                if reply is None:
                    raise ValueError('No response')
                value = json.loads(reply.get('response', ''))
                if (type(value) is list and len(value) == len(task['query']) and
                        all(type(v) is int and 0 <= v <= 31 for v in value)):
                    prediction = value
            except (ValueError, TypeError):
                # An ordinary clarification is an invalid prediction, not a
                # dropped episode. [] makes the official scorer count every
                # target cell wrong, just as the original recorded evaluation.
                pass
            row = dict(id=episode['id'], split=self.split, prediction=prediction,
                       reply=reply, error=error, seconds=time.perf_counter() - started)
            stream.write(json.dumps(row, separators=(',', ':')) + '\n')
            stream.flush()
            self.calls += 1
            return prediction

    assert 'cael_040' not in symbolic.get_symbolic_registry()
    # Register the new solver only. The official factory, loader, episode loop,
    # clone/zip_longest handling, metric denominators and report are unchanged.
    symbolic._SYMBOLIC_BASELINES['cael_040'] = CAELSymbolicAdapter
    harness = args.upstream / 'cellarc_baselines/scripts/eval_symbolic.py'
    sys.argv = [str(harness), 'baseline.name=cael_040',
                'dataset.include_metadata=false', 'dataset.root=' + args.dataset_root.as_posix(),
                'eval.max_episodes=null', 'eval.progress_bar=false',
                'eval.results_json_path=' + (args.output / 'official_metrics.json').as_posix(),
                'hydra.run.dir=' + (args.output / 'hydra').as_posix(), 'hydra.job.chdir=false']
    started = time.perf_counter()
    try:
        runpy.run_path(str(harness), run_name='__main__')
    finally:
        stream.close()
    assert [x.calls for x in instances] == [1000, 1000]
    for name, expected in source['files'].items():
        assert sha(args.cael_root / name) == expected, name
    for repo, entry in upstream['sources'].items():
        for name, expected in entry['files'].items():
            assert sha(args.upstream / repo / name) == expected['sha256'], (repo, name)
    metrics = json.loads((args.output / 'official_metrics.json').read_text(encoding='utf-8'))
    assert [x['episodes'] for x in metrics['splits']] == [1000, 1000]
    versions = {}
    for name in ['numpy', 'torch', 'hydra-core', 'omegaconf', 'tqdm', 'huggingface-hub']:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    receipt = dict(completed_utc=datetime.now(timezone.utc).isoformat(), complete=True,
                   version=__version__, python=sys.version, versions=versions,
                   official_harness_sha256=sha(harness), adapter_sha256=sha(__file__),
                   source_manifest_sha256=sha(args.source_manifest),
                   upstream_manifest_sha256=sha(args.upstream_manifest),
                   dataset_manifest_sha256=sha(args.dataset_manifest),
                   predictions_sha256=sha(args.output / 'predictions.jsonl'),
                   official_metrics_sha256=sha(args.output / 'official_metrics.json'),
                   episodes=2000, official_files_modified=False, model_source_modified=False,
                   model_inputs=['five support input/output pairs', 'query'],
                   gold_or_metadata_passed_to_model=False, offline=True,
                   elapsed_harness_seconds=time.perf_counter() - started,
                   purpose='Official-harness reproduction on viewed tasks; not new unseen evidence')
    (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(complete=True, episodes=2000, official_files_modified=False,
                          metrics=metrics['splits'])))


if __name__ == '__main__':
    main()
