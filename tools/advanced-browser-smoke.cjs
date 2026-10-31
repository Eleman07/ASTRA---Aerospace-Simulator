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
  page=await context.newPage();page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE:',e.message);});page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('404')){consoleErrors.push(m.text());console.error(m.text());}});
  await page.addInitScript(()=>{window.__pads=[{id:'Simulated Xbox Controller',index:0,mapping:'standard',connected:true,axes:[0,0,0,0],buttons:Array.from({length:18},()=>({value:0,pressed:false})),timestamp:1}];localStorage.setItem('astra-render-settings-v1',JSON.stringify({quality:'high',exposure:1}));Object.defineProperty(navigator,'getGamepads',{value:()=>window.__pads});});
  await page.goto(url,{waitUntil:'networkidle'});console.log('Loaded',url);
  async function stateWhen(predicate){const deadline=Date.now()+20000;let last;while(Date.now()<deadline){last=await page.evaluate(async()=>await (await fetch('/api/v1/state',{cache:'no-store'})).json());if(predicate(last))return last;await new Promise(r=>setTimeout(r,80));}throw Error('State predicate timeout: '+JSON.stringify({vehicle:last?.vehicle,time_s:last?.time_s,phase:last?.phase,command:last?.command}));}
  await page.waitForFunction(()=>document.querySelector('#simState')?.textContent==='READY',{timeout:30000});
  const graphics=await page.evaluate(()=>{const canvas=document.querySelector('#scene canvas'),gl=canvas?.getContext('webgl2');return {webgl2:!!gl,error:gl?.getError(),version:gl?.getParameter(gl.VERSION),renderer:gl?.getParameter(gl.RENDERER),width:canvas.width,height:canvas.height};});
  assert(graphics.webgl2,'Expected WebGL2, not the 2D fallback');assert.equal(graphics.error,0);

  async function sceneState(payload){const st=await page.evaluate(async p=>{const r=await fetch('/api/v1/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});const s=await r.json();if(!r.ok)throw Error(s.error);document.dispatchEvent(new CustomEvent('astra:engine-state',{detail:s}));return s;},payload);assert(st.science.enabled);assert.equal(Object.keys(st.science.disciplines).length,13);return st;}
  async function evidence(name){await page.waitForFunction(()=>{const c=document.querySelector('#scene canvas');if(!c?.dataset.pipeline)return false;const p=JSON.parse(c.dataset.pipeline);return p.shadows&&p.ssao&&p.fxaa;},{timeout:30000});const report=await page.evaluate(()=>{const c=document.querySelector('#scene canvas'),g=c.getContext('webgl2');return{pipeline:JSON.parse(c.dataset.pipeline),glError:g.getError(),width:c.width,height:c.height};});assert.equal(report.glError,0);await page.screenshot({path:path.join(output,name+'.png'),timeout:30000});return report;}
  const launch=await evidence('advanced-hdr-launch');
  await page.locator('#missionProfile').selectOption('planetary');await stateWhen(s=>s.scenario==='planetary');
  const lunarStart=await evidence('advanced-lunar-descent');assert(await page.locator('#visualVehicleModel').isHidden());assert(await page.locator('#lunarMissionVehicle').isVisible());
  const landed=await page.evaluate(async()=>{const post=async(p,v)=>(await(await fetch('/api/v1'+p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(v)})).json());await post('/launch',{});let s;for(let i=0;i<20;i++){s=await post('/step',{dt_s:5});if(s.phase==='LANDED'||s.phase==='CRASHED')break;}document.dispatchEvent(new CustomEvent('astra:engine-state',{detail:s}));return s;});assert.equal(landed.phase,'LANDED');
  const lunarContact=await evidence('advanced-lunar-contact');
  await page.locator('#missionProfile').selectOption('orbital');await stateWhen(s=>s.scenario==='orbital');
  const orbital=await evidence('advanced-hdr-orbital');
  await page.evaluate(()=>document.querySelector('.domain[data-kind="aircraft"]').click());await stateWhen(s=>s.vehicle==='aircraft'&&s.time_s===0);
  const aircraft=await evidence('advanced-hdr-aircraft');assert(await page.locator('#visualVehicleModel').isVisible());assert(await page.locator('#lunarMissionVehicle').isHidden());
  await page.evaluate(()=>document.querySelector('#tab-systems').click());await page.waitForFunction(()=>document.querySelectorAll('[data-science]').length===13);
  await page.screenshot({path:path.join(output,'advanced-science-panel.png'),timeout:30000});
  await page.evaluate(()=>document.querySelector('.render-settings select').value='low');await page.locator('.render-settings select').dispatchEvent('change');
  await page.waitForFunction(()=>{const p=JSON.parse(document.querySelector('#scene canvas').dataset.pipeline);return !p.shadows&&!p.ssao&&!p.bloom&&p.fxaa;});
  assert.deepEqual(errors,[]);assert.deepEqual(consoleErrors,[]);assert.deepEqual(external,[]);
  const report={packaged:!!exe,launch,lunarStart,lunarContact,orbital,aircraft,landing:{time_s:landed.time_s,speed_m_s:landed.touchdown_speed_m_s,error_m:Math.hypot(...landed.position_enu_m.slice(0,2))},external,pageErrors:errors,consoleErrors};fs.writeFileSync(path.join(output,'advanced-browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
 }catch(e){if(page){await page.screenshot({path:path.join(output,'browser-failure.png'),timeout:5000}).catch(()=>{});fs.writeFileSync(path.join(output,'browser-failure.html'),await page.content().catch(()=>''));}throw e;}finally{if(browser)await browser.close();server.kill();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
