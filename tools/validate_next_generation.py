"""Write reproducible scientific evidence with analytical values and SI units."""
from pathlib import Path
import json
import math
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from astra.engineering import beam_fem
from astra.nozzle import nozzle_design


def main():
    root=Path(__file__).resolve().parents[1]
    reference=1.875104068711961**2/(2*math.pi*2**2)*math.sqrt(70e9*(.1*.08**3/12)/(2700*.1*.08))
    modal=[]
    for n in (2,4,8,16):
        r=beam_fem({'elements':n})['modal'];error=abs(r['first_frequency_Hz']/reference-1)
        modal.append({'elements':n,'reference_Hz':reference,'computed_Hz':r['first_frequency_Hz'],
                      'relative_error':error,'relative_eigen_residual':r['relative_eigen_residual'],
                      'status':'PASS' if error<.001 and r['relative_eigen_residual']<1e-7 else 'FAIL'})
    flow=[]
    for pressure in (102000.,150000.,7000000.):
        r=nozzle_design({'chamber_pressure_Pa':pressure,'expansion_ratio':4.})
        flow.append({'chamber_pressure_Pa':pressure,'expansion_ratio':4.,'regime':r['flow_regime'],
                     'mass_flow_kg_s':r['exhaust_mass_flow_kg_s'],'exit_mach':r['exit_mach'],
                     'continuity_relative_error':r['mass_continuity_relative_residual'],
                     'status':'PASS' if r['mass_continuity_relative_residual']<1e-11 else 'FAIL'})
    report={'schema_version':1,'source':'ASTRA local deterministic solvers; analytical checks, not measured vehicle data',
            'beam':{'equations':'K phi = omega^2 M phi; f1 = beta1^2/(2*pi*L^2)*sqrt(E I/(rho A))',
                    'parameters':{'length_m':2.,'width_m':.1,'height_m':.08,'young_modulus_Pa':70e9,'density_kg_m3':2700.},
                    'assumptions':'Uniform small-deflection Euler-Bernoulli clamped-free beam, no shear/rotary inertia',
                    'method':'Hermite consistent mass, banded Cholesky inverse iteration','convergence':modal},
            'nozzle':{'equations':'mdot = rho_e A_e V_e; h0 = cp Te + Ve^2/2; normal-shock Rankine-Hugoniot + isentropic segments',
                      'parameters':{'specific_heat_ratio':1.22,'gas_constant_J_kgK':355.,'chamber_temperature_K':3400.,'throat_area_m2':.03,'altitude_m':0.},
                      'assumptions':'Steady calorically perfect gas; no viscous separation, combustion or oblique shocks',
                      'method':'Bracketed Mach and internal-shock area roots; 90 bisections','cases':flow},
            'references':[
                'https://www.grc.nasa.gov/www/k-12/airplane/mflchk.html',
                'https://www.grc.nasa.gov/www/k-12/airplane/normal.html',
                'https://lampz.tugraz.at/~hadley/memm/mechanics/cbeam.php'],
            'coupling':'New nozzle and beam modal calculations are independent Engineering Studio/snapshot studies. Existing live pressure-thrust coupling is retained; applied thrust telemetry drives graphics only.',
            'status':'PASS' if all(c['status']=='PASS' for c in modal+flow) else 'FAIL'}
    target=root/'docs'/'validation'/'next-generation.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Validation:',report['status'],target)
    if report['status']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
