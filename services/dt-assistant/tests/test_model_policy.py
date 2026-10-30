"""Policy rollout preserves safety/budgets and supports a no-paid switch."""
import importlib.util
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('model_policy',ROOT/'scripts/apply-model-policy.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


def test_merge_keeps_live_settings_and_supports_free_only(tmp_path):
    sales=tmp_path/'config/dt-assistant.yaml'; sales.parent.mkdir()
    base=yaml.safe_load((ROOT/'config/dt-assistant.yaml').read_text())
    base['budget']['monthly_usd']=3
    base['autonomy']['auto_intents']=[]
    base['custom_owner_setting']='keep'
    sales.write_text(yaml.safe_dump(base))
    hermes=tmp_path/'data/hermes/config.yaml'; hermes.parent.mkdir(parents=True)
    hermes.write_text(yaml.safe_dump({'model':{'provider':'nous'},'custom_owner_setting':'keep',
                                    'fallback_providers':[{'provider':'paid','model':'expensive'}]}))
    module.merge_policy(ROOT,tmp_path,free_only=True)
    actual=yaml.safe_load(sales.read_text()); h=yaml.safe_load(hermes.read_text())
    assert actual['budget']['monthly_usd']==3
    assert actual['autonomy']==base['autonomy']
    assert actual['custom_owner_setting']=='keep'
    assert not actual['routing']['allow_paid']
    assert h['model']['default']=='openrouter/free'
    assert h['custom_owner_setting']=='keep'
    assert h['fallback_model']=={} and 'fallback_providers' not in h
    assert h['provider_routing']['max_price']['prompt']==0
