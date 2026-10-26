/* npm install --prefix /tmp/astra-qa playwright
   NODE_PATH=/tmp/astra-qa/node_modules node tools/test_workspace_browser.cjs
   Serve the root with python3 -m http.server 8842 --bind 127.0.0.1 first. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
const base=process.env.ASTRA_URL||'http://127.0.0.1:8842';
const out=process.env.ASTRA_ARTIFACTS||'/tmp/astra-browser-results';fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
 const context=await browser.newContext({viewport:{width:1440,height:960}}),page=await context.newPage();const errors=[],checks=[];page.setDefaultTimeout(30000);
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
 await page.addInitScript(()=>localStorage.setItem('astra-locale','it'));
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#browserEngineStatus')?.textContent.includes('PYTHON 3.'),{},{timeout:60000});
 await page.waitForFunction(()=>document.querySelector('#ribbonAltitude')?.textContent.includes('1,5'),{},{timeout:30000});
 await page.waitForTimeout(2500);
 const api=(path,payload)=>page.evaluate(async({path,payload})=>{const {browserApi}=await import('./browser-api.js');return await browserApi(path,payload)},{path,payload});
 const sync=state=>page.evaluate(state=>document.dispatchEvent(new CustomEvent('astra:engine-state',{detail:state})),state);
 const shot=async name=>{await page.screenshot({path:out+'/'+name+'.png',fullPage:true});console.log(name,await page.locator('#visualModelSummary').textContent())};
 assert.equal(await page.locator('#scene canvas').evaluate(c=>!!c.getContext('webgl2')),true);checks.push('WebGL2 + Python Worker boot');
 for(const name of ['DATI','GNC','MODELLI','MISSIONE']){await page.getByRole('tab',{name,exact:true}).click();assert.equal(await page.locator('.workspace-pane:not(.workspace-inactive)').count(),1)}checks.push('All 4 workspace panels');
 await shot('01-rampa');
 await page.getByRole('tab',{name:'MODELLI',exact:true}).click();await page.locator('.system-assumptions summary').click();await page.locator('[name=bus_load_W]').fill('250');await page.locator('#systemsConfig button').click();await page.waitForFunction(()=>document.querySelector('#systemsConfigStatus').textContent.startsWith('Parametri applicati'));
 assert.equal((await api('/state')).live_systems.configuration.bus_load_W,250);checks.push('UI parameters reach Python');
 await page.locator('.system-assumptions summary').click();await page.locator('#play').click();await page.waitForFunction(()=>document.querySelector('#clock').textContent!=='T+ 00:00:00');await page.locator('#play').click();const paused=await api('/state');await page.waitForTimeout(300);assert.equal((await api('/state')).time_s,paused.time_s);checks.push('Start/pause preserves simulation time');
 await sync(await api('/step',{dt_s:20}));await shot('02-volo-modelli');
 await page.getByRole('tab',{name:'MISSIONE',exact:true}).click();await page.locator('#missionProfile').selectOption('orbital');await page.waitForFunction(()=>document.querySelector('#heroTitle').textContent.includes('Rendezvous'));
 await page.waitForTimeout(2500);await shot('03-orbita');
 await page.locator('#focusView').click();assert.equal(await page.locator('.right-hud').isVisible(),false);await shot('04-orbita-vista-libera');await page.locator('#focusView').click();checks.push('Focus view reversible');
 await page.locator('[data-kind=aircraft]').click();await page.waitForFunction(()=>document.querySelector('#ribbonResourceType').textContent==='PROPELLENTE');await page.waitForFunction(()=>document.querySelector('#visualModelSummary').textContent.includes('GLB pronto'),{},{timeout:90000});let state=await api('/state');assert.equal(state.vehicle,'aircraft');await shot('05-aereo');
 await page.locator('[data-kind=drone]').click();await page.waitForFunction(()=>document.querySelector('#ribbonResourceType').textContent==='BATTERIA');await page.locator('#openEngineeringStudio').click();await page.locator('#engineeringAnalysis').selectOption('robotics_route');
 await page.locator('#engineeringFields [name=grid_width]').fill('8');await page.locator('#engineeringFields [name=grid_height]').fill('8');await page.locator('#engineeringFields [name=obstacle_fraction]').fill('0');await page.locator('#engineeringFields [name=cell_size_m]').fill('1');await page.locator('#engineeringRun').click();await page.waitForFunction(()=>!document.querySelector('#engineeringDownload').disabled);await page.locator('#engineeringApplyRoute').click();await page.waitForFunction(()=>document.querySelector('#engineeringStatus').textContent.startsWith('ROTTA APPLICATA'));await page.locator('#engineeringClose').click();
 state=await api('/state');assert.ok(state.mission_route.coupled_into_flight_dynamics);await api('/launch',{});await sync(await api('/step',{dt_s:25}));await page.waitForTimeout(700);await shot('06-drone-rotta');
 for(let i=0;i<3;i++)state=await api('/step',{dt_s:60});await sync(state);assert.equal(state.phase,'LANDED');assert.ok(state.mission_route.completed);checks.push('UI A* route -> real UAV guidance -> LANDED');
 await page.locator('#disciplineExplorer').click();await page.locator('[data-discipline-filter=approx]').click();assert.equal(await page.locator('.discipline-card').count(),13);await page.locator('#closeDisciplines').click();checks.push('Parametric catalog still available');
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));await shot('07-mobile');assert.equal(await page.locator('#scene').evaluate(e=>Math.round(e.getBoundingClientRect().y)),58);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.getByRole('tab',{name:'MODELLI',exact:true}).click();await page.evaluate(()=>scrollTo(0,0));await shot('08-mobile-modelli');checks.push('390px layout, no horizontal overflow');
 assert.equal(await page.locator('#scene canvas').evaluate(c=>c.getContext('webgl2').getError()),0);assert.deepEqual(errors,[]);checks.push('No JS errors or WebGL errors');
 fs.writeFileSync(out+'/browser-report.json',JSON.stringify({checks,errors,viewport:[1440,960],mobile:[390,844],backend:'Pyodide Worker',gpu:'Chrome SwiftShader (software)',routeFinal:{phase:state.phase,position:state.position_ned_m,time_s:state.time_s}},null,2));console.log(JSON.stringify({checks,errors}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
