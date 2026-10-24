/* Hardware-neutral manual pilot input. Small gamepad noise must not drift the aircraft. */
export const deadzone = (x, threshold=0.15) => {
  if (!Number.isFinite(x)) return 0;
  const magnitude=Math.max(0,Math.min(1,Math.abs(x)));
  return magnitude<=threshold ? 0 : Math.sign(x)*(magnitude-threshold)/(1-threshold);
};
const pressed=(keys,code)=>keys.has(code)?1:0;
export function keyboardAxes(keys) {
  return {roll:pressed(keys,'KeyD')-pressed(keys,'KeyA'),
    pitch:pressed(keys,'KeyW')-pressed(keys,'KeyS'),
    yaw:pressed(keys,'KeyE')-pressed(keys,'KeyQ'),
    throttle:pressed(keys,'KeyR')-pressed(keys,'KeyF'),
    brakes:keys.has('KeyB')?1:0};
}
export function gamepadAxes(pad) {
  if(!pad || !pad.connected) return null;
  const a=pad.axes||[],b=pad.buttons||[];
  return {roll:deadzone(a[2]??0),pitch:-deadzone(a[3]??0),
    yaw:deadzone(a[0]??0),throttle:(b[7]?.value??0)-(b[6]?.value??0),
    brakes:b[0]?.pressed?1:0};
}
export function pilotStep(previous, axes, dt, kind) {
  const delta=Math.max(0,Math.min(0.1,dt));
  const bank=kind==='aircraft'?35:kind==='space'?35:27;
  const elevation=kind==='aircraft'?14:kind==='space'?30:24;
  const yawDelta=(kind==='space'?52:kind==='drone'?65:35)*axes.yaw*delta;
  const yaw=((previous.yaw+yawDelta+180)%360+360)%360-180;
  const target={roll:bank*axes.roll,pitch:elevation*axes.pitch,yaw,
    thrust:Math.max(0,Math.min(100,previous.thrust+axes.throttle*35*delta)),
    brakes:axes.brakes?100:0};
  return target;
}
