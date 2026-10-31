/* Run with Playwright installed; no browser automation dependency at runtime.
   ASTRA_TEST_EXE selects the packaged exe, otherwise uses source Python.
   ASTRA_BROWSER_CHANNEL=msedge selects the installed Windows browser. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),output=path.join(root,'test-results');fs.mkdirSync(output,{recursive:true});
async function main(){
 const exe=process.env.ASTRA_TEST_EXE;
 const server=spawn(exe||'python',exe?['--no-open','--port','0']:['windows_launcher.py','--no-open','--port','0'],{cwd:root,windowsHide:true,env:{...process.env,PYTHONUTF8:'1'}});
 let log='';server.stderr.on('data',d=>log+=d);
 let browser,page;
 try {
  const url=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('Server start timeout: '+log)),15000);server.stdout.on('data',d=>{log+=d;const match=log.match(/ASTRA OFFLINE: (http:\/\/127\.0\.0\.1:\d+)/);if(match){clearTimeout(timeout);resolve(match[1]);}});server.on('exit',code=>{clearTimeout(timeout);reject(Error('Server exited '+code+': '+log));});});
  browser=await chromium.launch({headless:true,channel:process.env.ASTRA_BROWSER_CHANNEL||undefined,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),external=[],errors=[],consoleErrors=[];
  await context.route('**/*',route=>{if(new URL(route.request().url()).hostname!=='127.0.0.1'){external.push(route.request().url());return route.abort();}return route.continue();});
  page=await context.newPage();page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE:',e.message);});page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('404'))consoleErrors.push(m.text());});
  await page.addInitScript(()=>{window.__pads=[{id:'Simulated Xbox Controller',index:0,mapping:'standard',connected:true,axes:[0,0,0,0],buttons:Array.from({length:18},()=>({value:0,pressed:false})),timestamp:1}];localStorage.setItem('astra-render-settings-v1',JSON.stringify({quality:'low',exposure:1}));Object.defineProperty(navigator,'getGamepads',{value:()=>window.__pads});});
  await page.goto(url,{waitUntil:'networkidle'});console.log('Loaded',url);
  async function stateWhen(predicate){const deadline=Date.now()+20000;let last;while(Date.now()<deadline){last=await page.evaluate(async()=>await (await fetch('/api/v1/state',{cache:'no-store'})).json());if(predicate(last))return last;await new Promise(r=>setTimeout(r,80));}throw Error('State predicate timeout: '+JSON.stringify({vehicle:last?.vehicle,time_s:last?.time_s,phase:last?.phase,command:last?.command}));}
  await page.waitForFunction(()=>document.querySelector('#simState')?.textContent==='READY',{timeout:30000});
  const graphics=await page.evaluate(()=>{const canvas=document.querySelector('#scene canvas'),gl=canvas?.getContext('webgl2');return {webgl2:!!gl,error:gl?.getError(),version:gl?.getParameter(gl.VERSION),renderer:gl?.getParameter(gl.RENDERER),width:canvas.width,height:canvas.height};});
  assert(graphics.webgl2,'Expected WebGL2, not the 2D fallback');assert.equal(graphics.error,0);
  await page.locator('#play').click();
  await stateWhen(s=>s.time_s>.5&&s.propulsion.applied_thrust_N>0);
  await page.screenshot({path:path.join(output,'windows-offline-launch.png')});
  await page.locator('#play').click();
  const controls=[];
  for(const kind of ['aircraft','drone','space']) {
    await page.evaluate(k=>document.querySelector(`.domain[data-kind="${k}"]`).click(),kind);
    await stateWhen(s=>s.vehicle===kind&&s.time_s===0);
    console.log('Opening controller');await page.getByRole('button',{name:'CONTROLLER',exact:true}).click({timeout:15000});console.log('Opened controller');
    await page.locator('[data-slot="primary"]').selectOption('0');
    await page.locator('[data-manual]').click();
    await page.locator('[data-arm]').click();console.log('Armed',kind);
    await page.waitForFunction(()=>document.querySelector('.top-actions button[title="Controller attivo"]'));
    await page.evaluate(()=>{const slider=document.querySelector('#thrust');slider.value='65';slider.dispatchEvent(new Event('input',{bubbles:true}));window.__pads[0].axes=[.75,-.5,.2,0];});
    await stateWhen(s=>s.command.mode==='manual'&&s.command.roll_deg>5&&s.command.pitch_deg>2);
    await page.locator('#play').click();
    const result=await stateWhen(s=>s.vehicle===kind&&s.time_s>1);
    assert(result.mission_started);
    assert(result.attitude_deg.every(Number.isFinite));controls.push({kind,time_s:result.time_s,command:result.command,attitude_deg:result.attitude_deg});
    await page.evaluate(()=>window.__pads=[]);
    await stateWhen(s=>s.command.mode==='auto');
    await page.locator('#play').click();
    await page.evaluate(()=>window.__pads=[{id:'Simulated Xbox Controller',index:0,mapping:'standard',connected:true,axes:[0,0,0,0],buttons:Array.from({length:18},()=>({value:0,pressed:false})),timestamp:1}]);
  }
  await page.locator('#missionProfile').selectOption('orbital');
  await stateWhen(s=>s.vehicle==='space'&&s.scenario==='orbital'&&s.time_s===0);
  await page.getByRole('button',{name:'CONTROLLER',exact:true}).click();
  await page.locator('[data-slot="primary"]').selectOption('0');
  await page.locator('[data-manual]').click();
  await page.locator('[data-arm]').click();
  await page.waitForFunction(()=>document.querySelector('.top-actions button[title="Controller attivo"]'));
  await page.evaluate(()=>{const slider=document.querySelector('#thrust');slider.value='0';slider.dispatchEvent(new Event('input',{bubbles:true}));window.__pads[0].axes=[.5,-.4,0,0];});
  await stateWhen(s=>s.command.attitude_target_deg[0]>5&&s.command.attitude_target_deg[1]>2);
  await page.locator('#play').click();
  const orbit=await stateWhen(s=>s.scenario==='orbital'&&s.time_s>1);
  assert(orbit.command.attitude_target_deg[0]>5&&orbit.command.attitude_target_deg[1]>2);
  assert(orbit.body_rates_rad_s.some(v=>Math.abs(v)>1e-6));
  controls.push({kind:'space-orbital',time_s:orbit.time_s,command:orbit.command,attitude_deg:orbit.attitude_deg,body_rates_rad_s:orbit.body_rates_rad_s});
  await page.evaluate(()=>window.__pads=[]);await stateWhen(s=>s.command.mode==='auto');await page.locator('#play').click();
  const studies=await page.evaluate(async()=>{const run=async payload=>await (await fetch('/api/v1/engineering',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})).json();return {beam:await run({analysis:'beam'}),nozzle:await run({analysis:'propulsion',chamber_pressure_Pa:300000,expansion_ratio:4})};});
  assert(studies.beam.modal.first_frequency_Hz>16&&studies.beam.modal.first_frequency_Hz<17);assert.equal(studies.nozzle.flow_regime,'CHOKED_INTERNAL_NORMAL_SHOCK');
  console.log('Opening controller');await page.getByRole('button',{name:'CONTROLLER',exact:true}).click({timeout:15000});console.log('Opened controller');
  await page.screenshot({path:path.join(output,'controller-manager.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(consoleErrors,[]);assert.deepEqual(external,[]);
  const report={packaged:!!exe,graphics,controls,externalRequests:external,pageErrors:errors,consoleErrors};
  fs.writeFileSync(path.join(output,'browser-smoke.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
 }catch(e){if(page){await page.screenshot({path:path.join(output,'browser-failure.png'),timeout:5000}).catch(()=>{});fs.writeFileSync(path.join(output,'browser-failure.html'),await page.content().catch(()=>''));}throw e;}finally{if(browser)await browser.close();server.kill();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
