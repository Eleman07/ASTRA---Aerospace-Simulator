"""6-DoF rigid-body powered landing engineering study (educational prototype).

Coordinates: inertial local Cartesian x/y tangent, z up; body +Z thrust axis.
Attitude: Hamilton scalar-first unit quaternion rotating body to inertial.
Nonlinear translation/rotation with constant-in-substep attitude control torques,
RK4, finite fuel and a terminal contact event (flat local datum).
"""
from __future__ import annotations
import math
from .advanced import scalar,_vec,_norm,_dot,_cross,_unit
G0=9.80665


def qmul(a,b):
    w,x,y,z=a; v,r,s,t=b
    return [w*v-x*r-y*s-z*t,w*r+x*v+y*t-z*s,w*s-x*t+y*v+z*r,w*t+x*s-y*r+z*v]


def conjugate(q): return [q[0],-q[1],-q[2],-q[3]]


def rotate(q,v):
    # Optimized quaternion vector rotation, q normalized, body -> inertial.
    u=q[1:]; t=_cross(u,v);t=[2*x for x in t];c=_cross(u,t)
    return [v[i]+q[0]*t[i]+c[i] for i in range(3)]


def align_z(vector):
    v=_unit(vector)
    if v[2]<-0.999999:return [0.,1.,0.,0.]
    cross=[-v[1],v[0],0.]
    q=[1.+v[2],*cross]
    norm=_norm(q)
    return [x/norm for x in q]


def planetary_landing_6dof(p:dict)->dict:
    g=scalar(p,'surface_gravity_m_s2',1.62,.01,30.)
    radius=scalar(p,'planet_radius_m',1737400.,1e4,1e9)
    z=scalar(p,'initial_altitude_m',900.,2.,1e6)
    x=scalar(p,'initial_east_m',95.,-1e6,1e6)
    y=scalar(p,'initial_north_m',-35.,-1e6,1e6)
    vx=scalar(p,'initial_east_speed_m_s',-2.,-1000.,1000.)
    vy=scalar(p,'initial_north_speed_m_s',0.,-1000.,1000.)
    vz=scalar(p,'initial_vertical_speed_m_s',-30.,-3000.,3000.)
    mass=scalar(p,'wet_mass_kg',1000.,10.,1e7)
    dry=scalar(p,'dry_mass_kg',650.,1.,1e7)
    thrust=scalar(p,'maximum_thrust_N',14500.,1.,1e9)
    isp=scalar(p,'specific_impulse_s',310.,20.,10000.)
    torque_limit=scalar(p,'maximum_body_torque_N_m',1800.,.01,1e7)
    inertia=_vec(p,'inertia_kg_m2',[900.,900.,500.],1e12)
    if any(a<=0 for a in inertia):raise ValueError('inertia components must be strictly positive')
    rho=scalar(p,'surface_density_kg_m3',0.,0.,15.)
    cd=scalar(p,'drag_coefficient',1.1,.01,5.)
    area=scalar(p,'drag_reference_area_m2',4.,0.,1e4)
    height_scale=scalar(p,'density_scale_height_m',10500.,100.,1e6)
    max_tilt=math.radians(scalar(p,'maximum_tilt_deg',25.,1.,80.))
    dt=scalar(p,'step_s',.05,.005,.25)
    duration=scalar(p,'maximum_duration_s',220.,1.,1800.)
    if dry>=mass:raise ValueError('dry_mass_kg must be smaller than wet_mass_kg')
    if thrust/dry <=g: raise ValueError('maximum thrust cannot support dry mass')
    # State: x,y,z,vx,vy,vz,qw,qx,qy,qz,wx,wy,wz,m
    state=[x,y,z,vx,vy,vz,1.,0.,0.,0.,0.,0.,0.,mass]
    samples=[];peak_q=0.;t=0.;status='time_limit';evidence=[]
    def record(cmd_thrust,cmd_tilt):
        return {'time_s':t,'east_m':state[0],'north_m':state[1],
                'altitude_m':max(0.,state[2]),'horizontal_speed_m_s':math.hypot(*state[3:5]),
                'vertical_speed_m_s':state[5],'body_to_inertial_quaternion':state[6:10],
                'angular_velocity_body_rad_s':state[10:13], 'mass_kg':state[13],
                'thrust_N':cmd_thrust,'commanded_tilt_deg':math.degrees(cmd_tilt)}
    def dynamics(yy,force,torques):
        xx,yn,zz,ux,uy,uz,qw,qx,qy,qz,wx,wy,wz,m=yy
        q=[qw,qx,qy,qz]
        active=force if m>dry+1e-9 else 0.
        inertial=rotate(q,[0.,0.,active])
        density=rho*math.exp(-max(0.,zz)/height_scale)
        vm=math.sqrt(ux*ux+uy*uy+uz*uz)
        drag_coeff=.5*density*cd*area*vm/max(m,1e-12)
        grav=g*(radius/(radius+max(zz,0.)))**2
        omega=[wx,wy,wz]
        qdot=qmul(q,[0.,wx,wy,wz])
        w_cross_Iw=_cross(omega,[inertia[i]*omega[i] for i in range(3)])
        ang=[(torques[i]-w_cross_Iw[i])/inertia[i] for i in range(3)]
        return [ux,uy,uz,inertial[0]/m-drag_coeff*ux,inertial[1]/m-drag_coeff*uy,
                inertial[2]/m-grav-drag_coeff*uz,*[.5*v for v in qdot],*ang,-active/(isp*G0)]
    samples.append(record(0.,0.))
    sample_interval=max(dt,duration/180.)
    next_sample=sample_interval
    for _ in range(min(360000, math.ceil(duration/dt)+2)):
        if t>=duration-1e-9:break
        zz=max(0.,state[2]);m=state[13]
        grav=g*(radius/(radius+zz))**2
        horizontal_dist=math.hypot(state[0],state[1])
        can_brake=max(.1,min(4.,thrust/m-grav))
        # Velocity tracking with distance-dependent vertical limit; hover briefly
        # above the pad if the horizontal error remains significant.
        speed_limit=min(32.,math.sqrt(max(.1,2*can_brake*.33*max(zz-3.,0.))))
        target_vz= -max(.8,speed_limit)
        if horizontal_dist>10 and zz<45:target_vz=min(target_vz,-.2)
        ax=max(-6.,min(6.,-.045*state[0]-.48*state[3]))
        ay=max(-6.,min(6.,-.045*state[1]-.48*state[4]))
        az=grav+min(12.,max(-8.,1.8*(target_vz-state[5])))
        az=max(.02,az)
        horizontal=math.hypot(ax,ay)
        max_horizontal=az*math.tan(max_tilt)
        if horizontal>max_horizontal:
            ax*=max_horizontal/horizontal;ay*=max_horizontal/horizontal
        desired=[ax,ay,az]
        desired_direction=_unit(desired)
        target_q=align_z(desired_direction)
        current_q=state[6:10]
        dq=qmul(target_q,conjugate(current_q))
        if dq[0]<0:dq=[-v for v in dq]
        omega=state[10:13]
        torques=[max(-torque_limit,min(torque_limit, 3800*2*dq[i+1]-1250*omega[i])) for i in range(3)]
        desired_force=m*_norm(desired)
        commanded=min(thrust,desired_force) if m>dry+1e-9 else 0.
        tilt=math.acos(max(-1.,min(1.,desired_direction[2])))
        h=min(dt,duration-t)
        if commanded>0:h=min(h,(m-dry)*isp*G0/commanded)
        if h<1e-10:
            state[13]=dry
            if dt<duration-t:h=min(dt,duration-t)
            else:break
        old=state[:]
        k1=dynamics(old,commanded,torques)
        k2=dynamics([old[i]+.5*h*k1[i] for i in range(14)],commanded,torques)
        k3=dynamics([old[i]+.5*h*k2[i] for i in range(14)],commanded,torques)
        k4=dynamics([old[i]+h*k3[i] for i in range(14)],commanded,torques)
        candidate=[old[i]+h*(k1[i]+2*k2[i]+2*k3[i]+k4[i])/6 for i in range(14)]
        if not all(math.isfinite(a) for a in candidate):raise ValueError('non-finite planetary integration state')
        if candidate[2]<=0:
            fraction=max(0.,min(1.,old[2]/max(old[2]-candidate[2],1e-9)))
            state=[old[i]+fraction*(candidate[i]-old[i]) for i in range(14)]
            state[2]=0.;t+=fraction*h
            status='touchdown';samples.append(record(commanded,tilt));break
        state=candidate
        norm=_norm(state[6:10]);state[6:10]=[v/norm for v in state[6:10]]
        state[13]=max(dry,state[13]);t+=h
        vm=_norm(state[3:6]);peak_q=max(peak_q,.5*rho*math.exp(-max(state[2],0.)/height_scale)*vm**2)
        if t>=next_sample-1e-9:
            samples.append(record(commanded,tilt));next_sample+=sample_interval
    if samples[-1]['time_s'] < t-1e-7:samples.append(record(commanded,tilt))
    hvel=math.hypot(state[3],state[4]);horizontal_error=math.hypot(state[0],state[1])
    touchdown_velocity=_norm(state[3:6]) if status=='touchdown' else None
    success=status=='touchdown' and touchdown_velocity<=3. and horizontal_error<=15.
    return {'solver':'Nonlinear 6-DoF rigid-body powered descent: quaternion attitude/RK4, finite fuel, torque-limited PD and thrust-vector guidance',
            'landing_status':'soft_landing' if success else ('hard_or_off_target_contact' if status=='touchdown' else status),
            'soft_landing':success,'touchdown_speed_m_s':touchdown_velocity,
            'horizontal_touchdown_error_m':horizontal_error,'final_altitude_m':state[2],
            'final_mass_kg':state[13],'propellant_used_kg':mass-state[13],
            'maximum_dynamic_pressure_Pa':peak_q,'elapsed_s':t,
            'samples':samples,
            'limits':'6-DoF rigid-body simulation with idealized directly commanded axial thrust and body torques; constant inertias, flat ground datum and terminal contact event. No landing-leg contact dynamics, time-delayed sensors, plume-surface interaction, true engine gimbal or DEM hazard avoidance. Guidance is PD, not optimal powered descent.'}
