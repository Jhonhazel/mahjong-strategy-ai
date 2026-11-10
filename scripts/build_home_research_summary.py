"""Reproduce small public chart facts from frozen reports, never training shards."""
import argparse
import json
from pathlib import Path

from scripts.lecturer_assets import file_hash,verify_assets


def build_summary(root):
    root=Path(root);verify_assets(root)
    paths={'metadata':'artifacts/models/mahjong_discard_mlp_v3.metadata.json',
           'contract':'datasets/expanded_strict_v2/data_contract.json',
           'quality':'datasets/expanded_strict_v2/data_quality_report.json',
           'history':'artifacts/phase2_2/training_history.json'}
    sources={key:json.loads((root/path).read_text()) for key,path in paths.items()}
    meta,contract,quality,history=(sources[k] for k in paths)
    history_sha=file_hash(root/paths['history']);contract_sha=file_hash(root/paths['contract'])
    if (history_sha!=meta['development']['history_sha256'] or contract_sha!=meta['dataset']['contract_sha256']
            or quality['status']!='PASS' or contract['status']!='READY'
            or quality['samples']!=contract['accepted_samples'] or quality['matches']!=contract['accepted_matches']):
        raise ValueError('Frozen dataset/history provenance mismatch')
    metrics=history['selected_train_metrics'];rows=[]
    if len(metrics['per_class'])!=34 or len(meta['tile_order'])!=34:raise ValueError('Expected34 discard classes')
    for index,row in enumerate(metrics['per_class']):
        count=row['support']
        if (row['class_id']!=index or row['tile']!=meta['tile_order'][index]
                or type(count) is not int or count<0 or sum(metrics['confusion_matrix'][index])!=count):
            raise ValueError('Training target histogram mismatch')
        rows.append({'class_index':index,'tile':row['tile'],'count':count})
    cohort=meta['training']['training_subset']
    if sum(r['count'] for r in rows)!=cohort['samples'] or history['train_samples']!=cohort['samples'] or history['train_matches']!=cohort['matches']:
        raise ValueError('Selected training cohort mismatch')
    partitions=[{'id':key,'samples':contract['splits'][key]['samples'],'matches':contract['splits'][key]['matches']}
                for key in ('train','validation','test','historical_test')]
    if sum(p['samples'] for p in partitions)!=contract['accepted_samples']:raise ValueError('Corpus partition total mismatch')
    return {'schema_version':1,'dataset_version':contract['dataset_version'],'dataset_id':contract['dataset_id'],
            'dataset_revision':contract['dataset_revision'],'contract_sha256':contract_sha,
            'model_checkpoint_sha256':meta['checkpoint_sha256'],'training_history_sha256':history_sha,
            'corpus':{'json_games':contract['source_games'],'matches':contract['accepted_matches'],
                      'samples':contract['accepted_samples'],'player_uids':quality['distinct_players']},
            'partitions':partitions,'training_cohort':{'experiment':Path(meta['development']['history_reference']).parent.name,
              'fold':meta['development']['fold_id'],'samples':cohort['samples'],'matches':cohort['matches']},
            'class_counts':rows,
            'method':'Ground-truth selected_train_metrics.per_class.support; checked against confusion matrix row sums and promoted training cohort. No shard scan or training.',
            'provenance':[{'path':path,'sha256':file_hash(root/path)} for path in paths.values()]}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    parser.add_argument('--output',type=Path);args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    path=args.output or root/'config/home_research.public.json'
    text=json.dumps(build_summary(root),indent=2,sort_keys=True)+'\n'
    if args.check:
        if path.read_text()!=text:raise ValueError('Public summary differs from frozen research sources')
    else:
        with path.open('x') as stream:stream.write(text)
    print(json.dumps({'status':'PASS','path':str(path.relative_to(root)) if path.is_relative_to(root) else str(path),'sha256':file_hash(path)}))


if __name__=='__main__':main()
