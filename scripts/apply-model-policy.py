#!/usr/bin/env python3
"""Merge committed free-first settings into live configs without touching credentials.

Back up before running. This does not restart/recreate containers. --free-only
removes the automatic paid fallback. Existing budgets and customer safety stay intact.
"""
import argparse
import os
from pathlib import Path
import tempfile
import yaml


def write(path, data):
    previous=path.stat()
    fd,name=tempfile.mkstemp(prefix='.model-policy-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as out:
            yaml.safe_dump(data,out,sort_keys=False,allow_unicode=True)
            out.flush(); os.fsync(out.fileno())
        os.chmod(name,previous.st_mode & 0o777)
        os.chown(name,previous.st_uid,previous.st_gid)
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)


def merge_policy(source, install, free_only=False, sales_only=False):
    sales_path=install/'config/dt-assistant.yaml'
    hermes_path=install/'data/hermes/config.yaml'
    sales=yaml.safe_load(sales_path.read_text()) or {}
    desired=yaml.safe_load((source/'config/dt-assistant.yaml').read_text())
    hermes=yaml.safe_load(hermes_path.read_text()) or {}
    hp=yaml.safe_load((source/'config/hermes-model-policy.yaml').read_text())
    required={'price','discount','order','complaint','legal','other'}
    if not required <= set(sales.get('autonomy',{}).get('never_auto',[])):
        raise SystemExit('Customer safety rule missing; refusing policy change')
    for key in ['routing','models']:
        sales[key]=desired[key]
    if free_only:
        sales['routing']['allow_paid']=False
        hp['fallback_model']={}
        hp['provider_routing']['max_price']={'prompt':0,'completion':0,'request':0}
    for key in ['model','fallback_model','provider_routing']:
        hermes[key]=hp[key]
    # Legacy fallback_providers overrides fallback_model in newer Hermes versions.
    hermes.pop('fallback_providers',None)
    for task, settings in hp['auxiliary'].items():
        hermes.setdefault('auxiliary',{}).setdefault(task,{}).update(settings)
    write(sales_path,sales)
    if not sales_only:
        write(hermes_path,hermes)
    print('Saved free-first model policy; customer safety, budgets and credentials preserved.')
    print('Paid fallback:',not free_only)
    print('Restart/rebuild services separately; existing Hermes sessions may retain their model.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--install-dir',type=Path,default=Path('/opt/sakir-ai'))
    p.add_argument('--free-only',action='store_true')
    p.add_argument('--sales-only',action='store_true',help='Preserve Hermes when its OpenRouter key is not provisioned')
    a=p.parse_args()
    merge_policy(a.source,a.install_dir,a.free_only,a.sales_only)
