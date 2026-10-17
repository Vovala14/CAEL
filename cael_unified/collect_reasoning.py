"""Collect licensed public text reasoning data; never extract arbitrary archives."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

from .bundle import ROOT
from .network import NETWORK
from urllib.parse import urlencode

SOURCES = [
 ('prontoqa.zip', 'https://raw.githubusercontent.com/asaparov/prontoqa/main/generated_ood_data.zip', 'Apache-2.0'),
 ('prontoqa_LICENSE.txt', 'https://raw.githubusercontent.com/asaparov/prontoqa/main/LICENSE', 'Apache-2.0'),
 ('babi.tar.gz', 'https://s3.amazonaws.com/text-datasets/babi_tasks_1-20_v1-2.tar.gz', 'CC BY 3.0'),
 ('babi_source_card.md', 'https://huggingface.co/datasets/facebook/babi_qa/raw/main/README.md', 'CC BY 3.0'),
 *[(f'ordering_{n}.json', f'https://raw.githubusercontent.com/google/BIG-bench/main/bigbench/benchmark_tasks/logical_deduction/{name}_objects/task.json', 'Apache-2.0')
   for n, name in [(3, 'three'), (5, 'five'), (7, 'seven')]],
 ('bigbench_LICENSE.txt', 'https://raw.githubusercontent.com/google/BIG-bench/main/LICENSE', 'Apache-2.0'),
]


def main():
    out = ROOT / 'research/reasoning_024'
    out.mkdir(parents=True, exist_ok=True)
    sources = []
    for filename, url, licence in SOURCES:
        if filename == 'babi_source_card.md':
            # Licensing was reviewed from the publisher's dataset card; do not
            # broaden the active runtime host list just for a copied README.
            continue
        path = out / filename
        if not path.exists():
            body = NETWORK.get(url, ttl=86400, timeout=60, max_bytes=160 * 1024 * 1024)
            path.write_bytes(body)
        sources.append(dict(file=filename, url=url, licence=licence, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size,
                            role='evaluation only' if filename.startswith('ordering_') else 'training data or licence notice'))
        print(json.dumps(sources[-1]), flush=True)
    with zipfile.ZipFile(out / 'prontoqa.zip') as archive:
        names = [dict(name=info.filename, bytes=info.file_size) for info in archive.infolist() if info.filename.endswith('.json')]
        (out / 'prontoqa_inventory.json').write_text(json.dumps(names, indent=2), encoding='utf-8')
        print('PrOntoQA JSON files', len(names), flush=True)
    with tarfile.open(out / 'babi.tar.gz','r:gz') as archive:
        names=[dict(name=m.name,bytes=m.size) for m in archive.getmembers() if '/en-10k/' in m.name and m.name.endswith('.txt')]
        (out/'babi_inventory.json').write_text(json.dumps(names,indent=2),encoding='utf-8')
    url = 'https://datasets-server.huggingface.co/rows?' + urlencode(dict(dataset='facebook/babi_qa', config='en-10k-qa1', split='train', offset=0, length=100))
    body = NETWORK.get(url, ttl=86400, timeout=30)
    (out / 'babi_sample.json').write_bytes(body)
    sources.append(dict(file='babi_sample.json', url=url, licence='CC BY 3.0', sha256=hashlib.sha256(body).hexdigest(), bytes=len(body),
                        licence_source='https://huggingface.co/datasets/facebook/babi_qa/blob/main/README.md'))
    (out / 'sources.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
