"""Live lunar powered descent; Hamilton quaternion body +Z thrust, local ENU SI.

Distinct from the offline engineering study: actuator lag, finite propellant,
mass-dependent inertia, noisy discrete navigation, event-localized ground contact.
"""
from __future__ import annotations
import math
import random
from .planetary_6dof import qmul, rotate, align_z, conjugate
from .science_models import norm, clamp, G0


class DescentNavigation:
    def __init__(self, state, seed):
        self.rng=random.Random(seed)
        self.x=[state[i] for i in range(6)]
        self.cov=[[[1.,0.],[0.,.1]] for _ in range(3)]
        self.next_fix=.05
        self.fixes=0

    def advance(self, h, acceleration, truth, time_s):
        for i in range(3):
            self.x[i]+=self.x[i+3]*h+.5*acceleration[i]*h*h
            self.x[i+3]+=acceleration[i]*h
            p=self.cov[i]
            q=.02**2
            self.cov[i]=[[p[0][0]+2*h*p[0][1]+h*h*p[1][1]+q*h**3/3,
                          p[0][1]+h*p[1][1]+q*h*h/2],
                         [p[1][0]+h*p[1][1]+q*h*h/2,p[1][1]+q*h]]
        if time_s+1e-10<self.next_fix:
            return
        self.next_fix+=.05
        self.fixes+=1
        # Independent position fixes (reference terrain/radar) and Doppler velocity.
        for i in range(3):
            for component, variance in ((0,.3**2),(1,.03**2)):
                p=self.cov[i]
                k=[p[j][component]/(p[component][component]+variance) for j in range(2)]
                index=i+3*component
                residual=truth[index]+self.rng.gauss(0,math.sqrt(variance))-self.x[index]
                self.x[i]+=k[0]*residual;self.x[i+3]+=k[1]*residual
                a=[[float(j==l)-k[j]*float(l==component) for l in range(2)] for j in range(2)]
                self.cov[i]=[[sum(a[j][k0]*p[k0][l0]*a[l][l0]
                    for k0 in range(2) for l0 in range(2))+k[j]*variance*k[l]
                    for l in range(2)] for j in range(2)]

    def snapshot(self):
        return dict(position_enu_m=self.x[:3],velocity_enu_m_s=self.x[3:],
            position_sigma_m=[math.sqrt(p[0][0]) for p in self.cov],
            velocity_sigma_m_s=[math.sqrt(p[1][1]) for p in self.cov],fixes=self.fixes,
            measurement_period_s=.05,model='3_AXIS_KALMAN_POSITION_DOPPLER_JOSEPH')


class PlanetaryMission:
    limits=('Reference Moon local ENU powered descent with variable gravity, mass-scaled '
            'reference inertia, bounded PD torque, first-order engine, noisy 20 Hz position/Doppler '
            'Kalman navigation and finite-fuel event-localized contact. Flat pad, no DEM, '
            'leg dynamics, terrain hazards, plume-surface interaction or optimal guidance.')
    def __init__(self, seed=42):
        self.y=[95.,-35.,900.,-2.,0.,-30.,1.,0.,0.,0.,0.,0.,0.,1000.]
        self.dry=650.;self.max_thrust=14500.;self.isp=310.
        self.engine_fraction=0.;self.thrust_N=0.;self.body_torques=[0.,0.,0.]
        self.contact=False;self.soft_landing=False;self.touchdown_speed=None
        self.time=0.;self.navigation=DescentNavigation(self.y,seed)
        self.last_acceleration=[0.,0.,-1.62]
        self.used_propellant=0.;self.rcs_used_kg=0.

    @staticmethod
    def gravity(altitude):
        return 1.62*(1737400/(1737400+max(0.,altitude)))**2

    @staticmethod
    def inertia(mass):
        return [600.+.8*max(0,mass-650),600.+.8*max(0,mass-650),350.+.4*max(0,mass-650)]

    def _guidance(self, command, power):
        x,y,z,vx,vy,vz=self.navigation.x
        g=self.gravity(z)
        if command['mode']=='auto':
            target_vz=-max(.7,min(28.,math.sqrt(max(.1,2*3*.33*max(z-3,0)))))
            if math.hypot(x,y)>10 and z<45:
                target_vz=-.2
            az=max(.05,g+clamp(1.8*(target_vz-vz),-8,12))
            ax,ay=clamp(-.045*x-.48*vx,-6,6),clamp(-.045*y-.48*vy,-6,6)
            horizontal=math.hypot(ax,ay);limit=az*math.tan(math.radians(25))
            if horizontal>limit:
                ax*=limit/horizontal;ay*=limit/horizontal
            desired=[ax,ay,az]
            force=min(self.max_thrust,self.y[13]*norm(desired))
            target=align_z(desired)
        else:
            force=clamp(command['throttle_pct']/100,0,1)*self.max_thrust
            target=align_z([math.tan(math.radians(clamp(command['roll_deg'],-25,25))),
                            math.tan(math.radians(clamp(command['pitch_deg'],-25,25))),1.])
        error=qmul(conjugate(self.y[6:10]),target)
        if error[0]<0:
            error=[-v for v in error]
        inertia=self.inertia(self.y[13])
        torque=[clamp(inertia[i]*(8*error[i+1]-3*self.y[10+i]),-1800,1800)*power for i in range(3)]
        return force if self.y[13]>self.dry else 0.,torque

    def _derivative(self,y,force,torque,mdot):
        m=max(self.dry,y[13]);q=y[6:10];qn=norm(q)
        q=[v/qn for v in q]
        f=rotate(q,[0.,0.,force])
        acceleration=[f[0]/m,f[1]/m,f[2]/m-self.gravity(y[2])]
        omega=y[10:13];inertia=self.inertia(m)
        iw=[inertia[i]*omega[i] for i in range(3)]
        cross=[omega[1]*iw[2]-omega[2]*iw[1],omega[2]*iw[0]-omega[0]*iw[2],omega[0]*iw[1]-omega[1]*iw[0]]
        idot=[-.8*mdot,-.8*mdot,-.4*mdot]
        wd=[(torque[i]-cross[i]-idot[i]*omega[i])/inertia[i] for i in range(3)]
        return [*y[3:6],*acceleration,*[.5*v for v in qmul(q,[0.,*omega])],*wd,-mdot]

    def _integrate(self,h,force,torque,mdot):
        y=self.y
        k1=self._derivative(y,force,torque,mdot)
        k2=self._derivative([y[i]+h*k1[i]/2 for i in range(14)],force,torque,mdot)
        k3=self._derivative([y[i]+h*k2[i]/2 for i in range(14)],force,torque,mdot)
        k4=self._derivative([y[i]+h*k3[i] for i in range(14)],force,torque,mdot)
        return [y[i]+h*(k1[i]+2*k2[i]+2*k3[i]+k4[i])/6 for i in range(14)]

    def advance(self,h,command,power=1.):
        if self.contact:
            return 0.
        target,torque=self._guidance(command,power)
        demand=target/self.max_thrust
        decay=math.exp(-h/.18)
        average=demand+(self.engine_fraction-demand)*.18*(1-decay)/h
        self.engine_fraction=demand+(self.engine_fraction-demand)*decay
        force=max(0.,average*self.max_thrust)
        rcs=norm(torque)/(220*G0*2.)
        mdot=force/(self.isp*G0)+rcs
        available=max(0.,self.y[13]-self.dry)
        if mdot*h>available:
            ratio=available/max(mdot*h,1e-30)
            force*=ratio;torque=[v*ratio for v in torque];mdot*=ratio;rcs*=ratio
            self.engine_fraction=0.
        candidate=self._integrate(h,force,torque,mdot)
        if candidate[2]<=0:
            lo,hi=0.,h
            for _ in range(32):
                mid=(lo+hi)/2
                if self._integrate(mid,force,torque,mdot)[2]>0:lo=mid
                else:hi=mid
            h=(lo+hi)/2;candidate=self._integrate(h,force,torque,mdot)
            candidate[2]=0.;self.contact=True
            self.touchdown_speed=norm(candidate[3:6])
            self.soft_landing=self.touchdown_speed<=3 and math.hypot(*candidate[:2])<=15
        candidate[13]=max(self.dry,candidate[13])
        qn=norm(candidate[6:10]);candidate[6:10]=[v/qn for v in candidate[6:10]]
        self.last_acceleration=self._derivative(candidate,force,torque,mdot)[3:6]
        self.y=candidate;self.time+=h;self.used_propellant+=mdot*h;self.rcs_used_kg+=rcs*h
        self.thrust_N=force;self.body_torques=torque
        self.navigation.advance(h,self.last_acceleration,self.y,self.time)
        return h

    def state(self):
        from .attitude import _euler_321_deg
        return dict(position_enu_m=self.y[:3],velocity_enu_m_s=self.y[3:6],
            position_ned_m=[self.y[1],self.y[0],-self.y[2]],
            altitude_m=max(0,self.y[2]),speed_m_s=norm(self.y[3:6]),
            mass_kg=self.y[13],propellant_kg=self.y[13]-self.dry,
            quaternion_body_to_enu=self.y[6:10],body_rates_rad_s=self.y[10:13],
            inertia_kg_m2=self.inertia(self.y[13]),attitude_deg=_euler_321_deg(self.y[6:10]),
            propulsion=dict(applied_thrust_N=self.thrust_N,maximum_thrust_N=self.max_thrust,
                specific_impulse_s=self.isp,engine_fraction=self.engine_fraction),
            navigation_estimate=self.navigation.snapshot(),rcs_propellant_used_kg=self.rcs_used_kg,
            contact=self.contact,soft_landing=self.soft_landing,touchdown_speed_m_s=self.touchdown_speed,
            environment=dict(body='Moon',density_kg_m3=0.,pressure_Pa=0.,temperature_K=250.,
                dynamic_pressure_Pa=0.,gravity_m_s2=self.gravity(self.y[2])),
            model_limits=self.limits)
