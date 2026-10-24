"""Stateless requirement verification with evidence bound to an ASTRA snapshot.

Checks only measurable scalar telemetry; records PASS/FAIL/NOT_EVALUATED and
source paths, but does not purport to certify vehicle requirements.
"""
from __future__ import annotations
import math
import re

_FIELD=re.compile(r'^[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*|\.[0-9]+)*$')
_OPS=('<=','>=','<','>','==','!=','between')


def _get_path(state:dict,path:str):
    if not isinstance(path,str) or len(path)>150 or not _FIELD.fullmatch(path):
        raise ValueError('field path invalid')
    node=state
    for key in path.split('.'):
        if isinstance(node,dict):node=node[key]
        elif isinstance(node,(list,tuple)) and key.isdigit():node=node[int(key)]
        else:raise KeyError(path)
    return node


def verify_requirements(snapshot:dict, requirements:list)->dict:
    if not isinstance(snapshot,dict):raise ValueError('snapshot must be a state object')
    if not isinstance(requirements,list) or not 1<=len(requirements)<=40:
        raise ValueError('requirements must be a list containing 1 to 40 checks')
    used=set();checks=[]
    for item in requirements:
        if not isinstance(item,dict):raise ValueError('each requirement must be an object')
        rid=item.get('id');field=item.get('field');op=item.get('operator');expected=item.get('value')
        unit=item.get('unit','')
        if not isinstance(rid,str) or not 1<=len(rid)<=72 or rid in used:
            raise ValueError('requirement IDs must be distinct strings (1–72 characters)')
        used.add(rid)
        if op not in _OPS:raise ValueError('unrecognized requirement operator')
        if not isinstance(unit,str) or len(unit)>30:raise ValueError('unit must be a short string')
        if op=='between':
            if not isinstance(expected,list) or len(expected)!=2:
                raise ValueError('between requires [minimum, maximum]')
            bounds=expected
        else:bounds=[expected]
        if any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) for x in bounds):
            raise ValueError('requirements must use finite numeric thresholds')
        if op=='between' and bounds[0]>bounds[1]:raise ValueError('between interval reversed')
        status='NOT_EVALUATED';actual=None
        try:
            actual=_get_path(snapshot,field)
            if isinstance(actual,bool) or not isinstance(actual,(int,float)) or not math.isfinite(actual):
                raise ValueError('field not a finite numeric measurement')
            passed={'<=':lambda:actual<=expected,'>=':lambda:actual>=expected,
                    '<':lambda:actual<expected,'>':lambda:actual>expected,
                    '==':lambda:actual==expected,'!=':lambda:actual!=expected,
                    'between':lambda:expected[0]<=actual<=expected[1]}[op]()
            status='PASS' if passed else 'FAIL'
        except (ValueError,KeyError,IndexError,TypeError):actual=None
        checks.append({'id':rid,'field':field,'operator':op,'threshold':expected,'actual':actual,
                       'unit':unit,'status':status,'evidence':f'ASTRA live state / {field}',
                       'simulation_time_s':snapshot.get('time_s')})
    passed=sum(row['status']=='PASS' for row in checks)
    failed=sum(row['status']=='FAIL' for row in checks)
    missing=sum(row['status']=='NOT_EVALUATED' for row in checks)
    return {'solver':'Stateless telemetry-based requirement traceability and predicate verification',
            'vehicle':snapshot.get('vehicle'),'simulation_time_s':snapshot.get('time_s'),
            'requirements':checks,'passed':passed,'failed':failed,'not_evaluated':missing,
            'verified':failed==0 and missing==0,
            'limits':'Snapshot-only acceptance checks, not a formal proof; no temporal logic, uncertainty propagation, certification, calibration or lifecycle requirement management.'}
