"""Analytical/independent residual checks, SI inputs, no external packages."""
import math
import unittest
from astra.nozzle import nozzle_design, _area_ratio, _shock_exit
from astra.engineering import beam_fem
from astra.engine import SimulationEngine


class NextGenerationPhysicsTests(unittest.TestCase):
    def test_sonic_convergent_nozzle(self):
        p={'specific_heat_ratio':1.4,'gas_constant_J_kgK':287.,'chamber_temperature_K':300.,
           'chamber_pressure_Pa':1e6,'throat_area_m2':.01,'expansion_ratio':1.}
        result=nozzle_design(p)
        expected=.01*1e6/math.sqrt(300)*math.sqrt(1.4/287)*(2/2.4)**3
        self.assertAlmostEqual(result['exhaust_mass_flow_kg_s'],expected,places=10)
        self.assertAlmostEqual(result['exit_mach'],1.,places=10)
        self.assertLess(result['mass_continuity_relative_residual'],1e-12)

    def test_unchoked_continuity_energy_and_pressure(self):
        result=nozzle_design({'chamber_pressure_Pa':102000.,'expansion_ratio':4.})
        self.assertEqual(result['flow_regime'],'UNCHOKED_SUBSONIC')
        self.assertLess(result['throat_mach'],1.)
        self.assertAlmostEqual(result['exit_pressure_Pa'],result['ambient_pressure_Pa'],places=6)
        cp=1.22*355/(1.22-1)
        self.assertAlmostEqual(cp*result['exit_temperature_K']+result['exit_velocity_m_s']**2/2,cp*3400,places=6)
        self.assertLess(result['mass_continuity_relative_residual'],1e-11)

    def test_internal_shock_pressure_root_and_entropy(self):
        r=nozzle_design({'chamber_pressure_Pa':300000.,'expansion_ratio':4.})
        self.assertEqual(r['flow_regime'],'CHOKED_INTERNAL_NORMAL_SHOCK')
        self.assertTrue(1<r['shock_area_over_throat_area']<4)
        self.assertLess(r['exit_total_pressure_Pa'],300000)
        self.assertAlmostEqual(r['exit_pressure_Pa'],r['ambient_pressure_Pa'],places=6)
        self.assertLess(r['mass_continuity_relative_residual'],1e-11)

    def test_supersonic_area_mach_reference(self):
        r=nozzle_design({'expansion_ratio':16.})
        self.assertEqual(r['flow_regime'],'CHOKED_SUPERSONIC')
        self.assertAlmostEqual(_area_ratio(r['exit_mach'],1.22),16,places=10)
        self.assertLess(r['mass_continuity_relative_residual'],1e-11)

    def test_flow_transition_continuity(self):
        # Solve the chamber pressure whose back-pressure equals each regime boundary.
        g=1.22;pa=nozzle_design({})['ambient_pressure_Pa'];ratio=4.
        shock_ratio=_shock_exit(ratio,ratio,g,1.)[1]
        from astra.nozzle import _subsonic_mach
        sub=_subsonic_mach(ratio,g);choke_ratio=(1+(g-1)*sub*sub/2)**(-g/(g-1))
        for boundary in (pa/shock_ratio,pa/choke_ratio):
            low=nozzle_design({'chamber_pressure_Pa':boundary*(1-1e-7),'expansion_ratio':ratio})
            high=nozzle_design({'chamber_pressure_Pa':boundary*(1+1e-7),'expansion_ratio':ratio})
            self.assertLess(abs(high['ideal_thrust_N']-low['ideal_thrust_N'])/high['ideal_thrust_N'],1e-4)

    def test_nozzle_rejects_invalid_and_backflow(self):
        for p in ({'chamber_pressure_Pa':1e4},{'specific_heat_ratio':float('nan')},{'throat_area_m2':True}):
            with self.assertRaises(ValueError):nozzle_design(p)

    def test_beam_analytical_deflection_and_reactions(self):
        r=beam_fem({'distributed_force_N_m':0})
        expected=-1000*2**3/(3*70e9*(.1*.08**3/12))
        self.assertAlmostEqual(r['tip_deflection_m'],expected,places=10)
        self.assertAlmostEqual(r['root_reaction_force_N'],1000,places=5)
        self.assertAlmostEqual(r['root_reaction_moment_N_m'],2000,places=5)

    def test_beam_modal_mesh_convergence(self):
        # Exact clamped-free EB characteristic root cos(beta)cosh(beta)=-1.
        beta=1.875104068711961
        reference=beta**2/(2*math.pi*2**2)*math.sqrt(70e9*(.1*.08**3/12)/(2700*.1*.08))
        errors=[]
        for n in (2,4,8,16):
            modal=beam_fem({'elements':n})['modal'];errors.append(abs(modal['first_frequency_Hz']/reference-1))
            self.assertLess(modal['relative_eigen_residual'],1e-7)
            self.assertAlmostEqual(modal['first_mode_tip_normalized'][-2],1.)
        self.assertTrue(all(b<a/8 for a,b in zip(errors,errors[1:])),errors)
        self.assertLess(errors[-1],2e-7)

    def test_modal_density_scaling(self):
        base=beam_fem({});dense=beam_fem({'density_kg_m3':10800})
        self.assertAlmostEqual(dense['modal']['first_frequency_Hz'],base['modal']['first_frequency_Hz']/2,places=8)
        self.assertAlmostEqual(dense['mass_kg'],4*base['mass_kg'])

    def test_manual_setpoints_change_real_vehicle_response(self):
        for vehicle in ('aircraft','drone','space'):
            a=SimulationEngine();b=SimulationEngine();a.reset(vehicle);b.reset(vehicle)
            a.launch();b.launch()
            a.set_command({'mode':'manual','throttle_pct':65,'roll_deg':0,'pitch_deg':0})
            b.set_command({'mode':'manual','throttle_pct':65,'roll_deg':15,'pitch_deg':8})
            for _ in range(30):a.step(.1);b.step(.1)
            self.assertNotEqual(a.state()['attitude_deg'],b.state()['attitude_deg'],vehicle)


if __name__=='__main__':unittest.main()
