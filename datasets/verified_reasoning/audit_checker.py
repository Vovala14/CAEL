"""Reproduce targeted legacy/current checker comparisons; no model execution."""
import importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import verify,test_verify
spec=importlib.util.spec_from_file_location('legacy',HERE/'verify_legacy_v1_1.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def main():
    results=[]
    for case in test_verify.CASES:
        try:baseline=old.check(case['reply'],case['row']);error=None
        except Exception as exc:baseline=None;error=type(exc).__name__
        current=verify.judge(case['reply'],case['row'])
        assert (current['status']=='correct')==case['expected'],case['id']
        results.append({'id':case['id'],'expected_accept':case['expected'],'legacy_accept':baseline,'legacy_error':error,'current':current})
    summary={'targeted_cases':len(results),'passed_current':len(results),'legacy_disagreements':sum(r['legacy_accept']!=r['expected_accept'] for r in results),'sampling':'Failure-seeking semantic regressions and positive equivalents, not random real completions; no population error-rate estimate. This suite is not John6666’s separate 29-case audit.','legacy_revision':'31780cd0fed31c04a50deafd3c27f75f33a84825','current_version':verify.VERSION,'cases':results}
    (HERE/'checker_regression_audit.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k!='cases'}))
if __name__=='__main__':main()
