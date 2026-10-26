"""Bind an A* design route to the existing UAV position controller.

Waypoints are translated to launch-local N/E. Synthetic obstacles remain a
planning illustration; waypoint tracking is not collision avoidance or SLAM.
"""
import copy
import math

class MissionRoute:
    def __init__(self, plan):
        points=plan.get('waypoints_m')
        if not plan.get('found') or not isinstance(points,list) or not 2<=len(points)<=512:
            raise ValueError('A found route with 2–512 waypoints is required')
        if not all(isinstance(p,list) and len(p)==2 and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in p) for p in points):
            raise ValueError('Waypoints must be finite N/E pairs')
        origin=points[0]
        outbound=[[p[i]-origin[i] for i in range(2)] for p in points]
        if max(math.hypot(*p) for p in outbound)>500:
            raise ValueError('Live inspection route must stay within 500 m of the pad')
        self.outbound=outbound
        self.points=outbound+list(reversed(outbound[:-1]))
        self.index=1
        self.finished=False
        self.error_m=0.
        self.seed=plan.get('seed')

    def target(self, position, velocity):
        point=self.points[self.index]
        self.error_m=math.dist(position,point)
        # Arrive and settle: no time-based waypoint skipping.
        if self.error_m<.7 and math.hypot(*velocity)<.8:
            if self.index==len(self.points)-1:
                self.finished=True
            else:
                self.index+=1
        return list(self.points[self.index])

    def snapshot(self):
        return {'model':'ASTAR_WAYPOINTS_TO_EXISTING_LQR_GNC',
                'coupled_into_flight_dynamics':True,
                'waypoints_ned_m':copy.deepcopy(self.outbound),
                'altitude_m':30.,'active_index':self.index,
                'total_waypoints':len(self.points),
                'target_ned_m':list(self.points[self.index]),
                'tracking_error_m':self.error_m,'completed':self.finished,'seed':self.seed,
                'limits':'Point waypoint tracking, synthetic 2D plan; no collision guarantee, SLAM or 3D obstacle sensing'}
